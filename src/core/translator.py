"""Temiz ve stabilize çeviri altyapısı (Google + stub motorlar + cache + adaptif concurrency)."""

from __future__ import annotations

import asyncio
import aiohttp
import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from collections import OrderedDict, deque


class TranslationEngine(Enum):
    GOOGLE = "google"
    DEEPL = "deepl"
    YANDEX = "yandex"
    BING = "bing"
    LIBRETRANSLATOR = "libre"
    # DEEP_TRANSLATOR removed


@dataclass
class TranslationRequest:
    text: str
    source_lang: str
    target_lang: str
    engine: TranslationEngine
    metadata: Dict = field(default_factory=dict)


@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    engine: TranslationEngine
    success: bool
    error: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict = field(default_factory=dict)


class BaseTranslator(ABC):
    def __init__(self, api_key: Optional[str] = None, proxy_manager=None):
        self.api_key = api_key
        self.proxy_manager = proxy_manager
        self.use_proxy = True
        self.logger = logging.getLogger(self.__class__.__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(limit=256, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(connector=self._connector, timeout=timeout)
        return self._session

    async def close(self):
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
            self._connector = None

    def set_proxy_enabled(self, enabled: bool):
        self.use_proxy = enabled

    async def _make_request(self, url: str, method: str = "GET", **kwargs):
        session = await self._get_session()
        proxy = None
        if self.use_proxy and self.proxy_manager:
            p = self.proxy_manager.get_next_proxy()
            if p:
                proxy = p.url
        if method.upper() == "GET":
            async with session.get(url, proxy=proxy, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                raise RuntimeError(f"HTTP {resp.status}")
        elif method.upper() == "POST":
            async with session.post(url, proxy=proxy, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                raise RuntimeError(f"HTTP {resp.status}")
        else:
            raise ValueError("Unsupported method")

    @abstractmethod
    async def translate_single(self, request: TranslationRequest) -> TranslationResult: ...

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        return [await self.translate_single(r) for r in requests]

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]: ...


class GoogleTranslator(BaseTranslator):
    base_url = "https://translate.googleapis.com/translate_a/single"
    multi_q_concurrency = 8  # Aynı anda kaç multi-q isteği
    max_slice_chars = 6000   # Her slice toplam karakter limiti

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        params = {'client':'gtx','sl':request.source_lang,'tl':request.target_lang,'dt':'t','q':request.text}
        try:
            query = urllib.parse.urlencode(params, doseq=True, safe='')
            data = await self._make_request(f"{self.base_url}?{query}")
            if data and isinstance(data, list) and data and data[0]:
                text = ''.join(part[0] for part in data[0] if part and part[0])
                return TranslationResult(request.text, text, request.source_lang, request.target_lang, TranslationEngine.GOOGLE, True, confidence=0.9, metadata=request.metadata)
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.GOOGLE, False, "Parse failure", metadata=request.metadata)
        except Exception:
            import requests
            try:
                def do():
                    return requests.get(self.base_url, params=params, timeout=5, headers={'User-Agent':'Mozilla/5.0'})
                resp = await asyncio.to_thread(do)
                if resp.status_code == 200:
                    data2 = resp.json()
                    if data2 and isinstance(data2, list) and data2 and data2[0]:
                        text = ''.join(part[0] for part in data2[0] if part and part[0])
                        return TranslationResult(request.text, text, request.source_lang, request.target_lang, TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata)
                return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.GOOGLE, False, f"HTTP {resp.status_code}", metadata=request.metadata)
            except Exception as e2:
                return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.GOOGLE, False, str(e2), metadata=request.metadata)

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Optimize edilmiş toplu çeviri:
        1. Aynı metinleri tek sefer çevir (dedup)
        2. Büyük listeyi karakter limitine göre slice'lara böl
        3. Slice'ları paralel (bounded) multi-q istekleriyle çalıştır
        4. Orijinal sıra korunur
        """
        if not requests:
            return []
        # Dil çifti karışık ise fallback
        sl = {r.source_lang for r in requests}; tl = {r.target_lang for r in requests}
        if len(sl) > 1 or len(tl) > 1:
            return await super().translate_batch(requests)

        # Deduplikasyon
        indexed = list(enumerate(requests))
        unique_map: Dict[str, int] = {}
        unique_list: List[Tuple[int, TranslationRequest]] = []
        dup_links: Dict[int, int] = {}  # original_index -> unique_index
        for idx, req in indexed:
            key = req.text
            if key in unique_map:
                dup_links[idx] = unique_map[key]
            else:
                u_index = len(unique_list)
                unique_map[key] = u_index
                unique_list.append((idx, req))
                dup_links[idx] = u_index

        # Slice oluştur
        slices: List[List[Tuple[int, TranslationRequest]]] = []
        cur: List[Tuple[int, TranslationRequest]] = []
        cur_chars = 0
        for item in unique_list:
            text_len = len(item[1].text)
            if cur and cur_chars + text_len > self.max_slice_chars:
                slices.append(cur)
                cur = []
                cur_chars = 0
            cur.append(item)
            cur_chars += text_len
        if cur:
            slices.append(cur)

        # Paralel çalıştır (bounded)
        sem = asyncio.Semaphore(self.multi_q_concurrency)

        async def run_slice(slice_items: List[Tuple[int, TranslationRequest]]):
            async with sem:
                reqs = [r for _, r in slice_items]
                results = await self._multi_q(reqs)
                # slice içindeki index eşleşmesi (aynı uzunluk varsayımı)
                return [(slice_items[i][0], results[i]) for i in range(len(results))]

        tasks = [asyncio.create_task(run_slice(s)) for s in slices]
        gathered: List[List[Tuple[int, TranslationResult]]] = await asyncio.gather(*tasks)
        # Unique sonuç tablosu (unique sıraya göre)
        unique_results: Dict[int, TranslationResult] = {}
        for lst in gathered:
            for orig_idx, res in lst:
                # orig_idx burada unique_list içindeki orijinal global indeks değil; unique_list'te kaydettiğimiz idx
                # slice_items'te (global_index, request) vardı => orig_idx global index
                # unique index'i bulmak için dup_links'den tersine gerek yok; map oluşturalım
                # Hız için text'e göre de eşleyebilirdik; burada global index'ten unique index'e gidelim
                # unique index bul:
                # performans için bir kere hesaplanıyor
                pass

        # Daha hızlı yol: unique_list sırasına göre slice çıktılarından doldur
        # unique_list[i][0] = global index; onun sonucunu bulmak için hashedict
        global_to_result: Dict[int, TranslationResult] = {}
        for lst in gathered:
            for global_idx, res in lst:
                global_to_result[global_idx] = res

        # Şimdi tüm orijinal indeksleri sırayla doldururken dedup'u kopyala
        final_results: List[TranslationResult] = [None] * len(requests)  # type: ignore
        for original_idx, req in indexed:
            unique_idx = dup_links[original_idx]
            unique_global_index = unique_list[unique_idx][0]
            base_res = global_to_result[unique_global_index]
            if base_res is None:
                # Güvenlik fallback
                final_results[original_idx] = TranslationResult(req.text, "", req.source_lang, req.target_lang, TranslationEngine.GOOGLE, False, "Missing base result")
            else:
                # Aynı referansı paylaşmak yerine kopya (metadata farklı olabilir)
                final_results[original_idx] = TranslationResult(
                    original_text=req.text,
                    translated_text=base_res.translated_text,
                    source_lang=req.source_lang,
                    target_lang=req.target_lang,
                    engine=base_res.engine,
                    success=base_res.success,
                    error=base_res.error,
                    confidence=base_res.confidence,
                    metadata=req.metadata
                )
        return final_results

    async def _multi_q(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        if not batch: return []
        if len(batch) == 1: return [await self.translate_single(batch[0])]
        params: List[Tuple[str,str]] = [('client','gtx'),('sl',batch[0].source_lang),('tl',batch[0].target_lang),('dt','t')]
        for r in batch: params.append(('q', r.text))
        query = urllib.parse.urlencode(params, doseq=True, safe='')
        try:
            data = await self._make_request(f"{self.base_url}?{query}")
            segs = data[0] if isinstance(data, list) and data else None
            if not segs: raise ValueError('no segments')
            originals = [r.text for r in batch]
            mapped = [""]*len(batch)
            idx=0; acc_o=""; acc_t=""
            for seg in segs:
                if not seg or len(seg)<2: continue
                tpart, opart = seg[0], seg[1]
                if opart is None: continue
                acc_o += opart; acc_t += tpart
                if idx < len(originals) and acc_o == originals[idx]:
                    mapped[idx]=acc_t; idx+=1; acc_o=""; acc_t=""; 
                    if idx>=len(originals): break
                elif idx < len(originals) and len(acc_o) > len(originals[idx]) + 20:
                    raise ValueError('align fail')
            if any(not m for m in mapped): raise ValueError('incomplete')
            return [TranslationResult(r.text, t, r.source_lang, r.target_lang, TranslationEngine.GOOGLE, True, confidence=0.9) for r,t in zip(batch,mapped)]
        except Exception:
            return await super().translate_batch(batch)

    def get_supported_languages(self) -> Dict[str,str]:
        return {'auto':'Auto','en':'English','tr':'Turkish'}


class DeepLTranslator(BaseTranslator):
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, "API key required")
        return TranslationResult(request.text, request.text, request.source_lang, request.target_lang, TranslationEngine.DEEPL, True, confidence=0.5)

    def get_supported_languages(self) -> Dict[str,str]: return {'en':'English','tr':'Turkish'}


class YandexTranslator(BaseTranslator):
    base_url = "https://translate.yandex.net/api/v1.5/tr.json/translate"
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, "API key required")
        import requests
        try:
            lang_pair = f"{request.source_lang}-{request.target_lang}" if request.source_lang != 'auto' else request.target_lang
            params = {'key': self.api_key,'text':request.text,'lang':lang_pair,'format':'plain'}
            proxies=None
            if self.use_proxy and self.proxy_manager:
                p=self.proxy_manager.get_next_proxy();
                if p: proxies={'http':p.url,'https':p.url}
            resp = await asyncio.to_thread(lambda: requests.post(self.base_url,data=params,timeout=10,proxies=proxies))
            if resp.status_code==200:
                data=resp.json()
                if data.get('code')==200 and 'text' in data:
                    txt=' '.join(data['text'])
                    return TranslationResult(request.text, txt, request.source_lang, request.target_lang, TranslationEngine.YANDEX, True, confidence=0.9)
                return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, data.get('message','API error'))
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, f"HTTP {resp.status_code}")
        except Exception as e:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.YANDEX, False, str(e))

    def get_supported_languages(self) -> Dict[str,str]: return {'auto':'Auto','en':'English','tr':'Turkish'}


class BingTranslator(BaseTranslator):
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.BING, False, "Not implemented")
    def get_supported_languages(self) -> Dict[str,str]: return {'en':'English','tr':'Turkish'}


class LibreTranslator(BaseTranslator):
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(request.text, request.text, request.source_lang, request.target_lang, TranslationEngine.LIBRETRANSLATOR, True, confidence=0.5)
    def get_supported_languages(self) -> Dict[str,str]: return {'en':'English','tr':'Turkish'}




    




class TranslationManager:
    def __init__(self, proxy_manager=None):
        self.proxy_manager = proxy_manager
        self.logger = logging.getLogger(__name__)
        self.translators: Dict[TranslationEngine, BaseTranslator] = {}
        self.max_retries = 1
        self.retry_delays = [0.1,0.2]
        self.max_batch_size = 500
        self.max_concurrent_requests = 256
        self.cache_capacity = 20000
        self._cache: OrderedDict = OrderedDict()
        self._cache_lock = asyncio.Lock()
        self.cache_hits = 0
        self.cache_misses = 0
        # Adaptive
        self.adaptive_enabled = True
        self.max_concurrency_cap = 512
        self.min_concurrency_floor = 4
        self._recent_metrics = deque(maxlen=500)
        self._adapt_lock = asyncio.Lock()
        self._last_adapt_time = 0.0
        self.adapt_interval_sec = 5.0

    def add_translator(self, engine: TranslationEngine, translator: BaseTranslator):
        self.translators[engine] = translator

    def remove_translator(self, engine: TranslationEngine):
        self.translators.pop(engine, None)

    def set_proxy_enabled(self, enabled: bool):
        for t in self.translators.values():
            t.set_proxy_enabled(enabled)

    def set_max_concurrency(self, value: int):
        self.max_concurrent_requests = max(1, int(value))

    async def close_all(self):
        tasks = []
        for t in self.translators.values():
            if hasattr(t, 'close'):
                tasks.append(t.close())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _cache_get(self, key: Tuple[str,str,str,str]) -> Optional[TranslationResult]:
        async with self._cache_lock:
            val = self._cache.get(key)
            if val:
                self._cache.move_to_end(key)
            return val

    async def _cache_put(self, key: Tuple[str,str,str,str], val: TranslationResult):
        if not val.success:
            return
        async with self._cache_lock:
            self._cache[key] = val
            self._cache.move_to_end(key)
            if len(self._cache) > self.cache_capacity:
                self._cache.popitem(last=False)

    async def translate_with_retry(self, req: TranslationRequest) -> TranslationResult:
        tr = self.translators.get(req.engine)
        if not tr:
            return TranslationResult(req.text, "", req.source_lang, req.target_lang, req.engine, False, f"Translator {req.engine.value} not available")
        key = (req.engine.value, req.source_lang, req.target_lang, req.text)
        cached = await self._cache_get(key)
        if cached:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        last_err = None
        start = time.time()
        for attempt in range(self.max_retries + 1):
            try:
                res = await tr.translate_single(req)
                if res.success:
                    await self._cache_put(key, res)
                    await self._record_metric(time.time() - start, True)
                    return res
                last_err = res.error
            except Exception as e:
                last_err = str(e)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
        await self._record_metric(time.time() - start, False)
        return TranslationResult(req.text, "", req.source_lang, req.target_lang, req.engine, False, f"Failed: {last_err}")

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        if not requests:
            return []
        indexed = list(enumerate(requests))
        groups: Dict[TranslationEngine, List[Tuple[int, TranslationRequest]]] = {}
        for i, r in indexed:
            groups.setdefault(r.engine, []).append((i, r))
        buffer: List[Tuple[int, TranslationResult]] = []
        for engine, items in groups.items():
            tr = self.translators.get(engine)
            if not tr:
                for idx, r in items:
                    buffer.append((idx, TranslationResult(r.text, "", r.source_lang, r.target_lang, r.engine, False, f"Translator {engine.value} not available")))
                continue
            only = [r for _, r in items]
            used_batch = False
            if isinstance(tr, GoogleTranslator) and len(only) > 1:
                try:
                    bout = await tr.translate_batch(only)
                    if bout and len(bout) == len(only):
                        for (idx, _), res in zip(items, bout):
                            if res.success:
                                key2 = (res.engine.value, res.source_lang, res.target_lang, res.original_text)
                                await self._cache_put(key2, res)
                            buffer.append((idx, res))
                        used_batch = True
                except Exception as e:
                    self.logger.debug(f"Batch fail {engine.value}: {e}")
            
            # No special-case for Deep-Translator; use generic per-request handling
            if used_batch:
                continue
            sem = asyncio.Semaphore(self.max_concurrent_requests)
            async def run_single(ix: int, rq: TranslationRequest):
                async with sem:
                    return ix, await self.translate_with_retry(rq)
            results = await asyncio.gather(*[run_single(i, r) for i, r in items])
            buffer.extend(results)
        await self._maybe_adapt_concurrency()
        buffer.sort(key=lambda x: x[0])
        return [r for _, r in buffer]

    def get_cache_stats(self) -> Dict[str, float]:
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total else 0.0
        return {'size': len(self._cache), 'capacity': self.cache_capacity, 'hits': self.cache_hits, 'misses': self.cache_misses, 'hit_rate': round(hit_rate, 2)}

    async def _record_metric(self, dur: float, ok: bool):
        if not self.adaptive_enabled:
            return
        self._recent_metrics.append((dur, ok))
        if len(self._recent_metrics) % 25 == 0:
            await self._maybe_adapt_concurrency()

    async def _maybe_adapt_concurrency(self):
        if not self.adaptive_enabled:
            return
        now = time.time()
        if now - self._last_adapt_time < self.adapt_interval_sec:
            return
        if len(self._recent_metrics) < 20:
            return
        async with self._adapt_lock:
            now2 = time.time()
            if now2 - self._last_adapt_time < self.adapt_interval_sec:
                return
            durations = [d for d, _ in self._recent_metrics]
            successes = [s for _, s in self._recent_metrics]
            avg_latency = sum(durations) / len(durations)
            fail_rate = 1 - (sum(1 for s in successes if s) / len(successes))
            old = self.max_concurrent_requests
            new = old
            if fail_rate > 0.2 or avg_latency > 1.5:
                new = max(self.min_concurrency_floor, int(old * 0.8))
            elif fail_rate < 0.05 and avg_latency < 0.5:
                new = min(self.max_concurrency_cap, max(old + 1, int(old * 1.1)))
            if new != old:
                self.max_concurrent_requests = new
                self.logger.info(f"Adaptive concurrency {old} -> {new} (lat={avg_latency:.3f}s fail={fail_rate:.2%})")
            self._last_adapt_time = time.time()
