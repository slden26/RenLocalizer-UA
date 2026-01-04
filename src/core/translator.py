"""Temiz ve stabilize çeviri altyapısı (Google + stub motorlar + cache + adaptif concurrency)."""

from __future__ import annotations

import asyncio
import aiohttp
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from collections import OrderedDict, deque


# Ren'Py değişken ve tag koruma regex'leri
# [variable], [player], [lang_lady] gibi interpolation değişkenleri
RENPY_VAR_PATTERN = re.compile(r'\[([^\[\]]+)\]')
# {tag}, {i}, {b}, {color=#fff} gibi text tag'leri
RENPY_TAG_PATTERN = re.compile(r'\{([^\{\}]+)\}')
# {{escaped}} çift parantez
RENPY_ESCAPED_PATTERN = re.compile(r'\{\{|\}\}')
# ?V000? / ?T000? / ?F000? gibi runtime placeholder'lar
RENPY_QMARK_PLACEHOLDER_RE = re.compile(r'\?[A-Za-z]\d{3}\?')
# ⟦V000⟧ gibi açılı parantez placeholder'lar
RENPY_ANGLE_PLACEHOLDER_RE = re.compile(r'\u27e6[^\u27e7]+\u27e7')


def protect_renpy_syntax(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Ren'Py değişkenlerini ve tag'lerini çeviriden korur.
    Placeholder'larla değiştirir ve geri dönüşüm sözlüğü döner.
    """
    # Single-pass scanning to avoid nested replacement collisions.
    placeholders: Dict[str, str] = {}
    counter = 0

    # Match order: escaped braces '{{' or '}}', full tags '{...}', square vars '[...]',
    # Ren'Py qmark placeholders (?V000?, ?T000?) and angled placeholders (⟦V000⟧)
    combined = re.compile(
        r'(\{\{|\}\}|\{[^\}]+\}|\[[^\[\]]+\]|'
        r'\?[A-Za-z]\d{3}\?|'
        r'\u27e6[^\u27e7]+\u27e7)'
    )
    out_parts: List[str] = []
    last = 0
    for m in combined.finditer(text):
        start, end = m.start(), m.end()
        # Append text between matches
        out_parts.append(text[last:start])
        token = m.group(0)
        if token in ('{{', '}}'):
            prefix = 'ESC'
        elif token.startswith('{') and token.endswith('}'):
            prefix = 'TAG'
        else:
            prefix = 'VAR'
        key = f"XRPYX{prefix}{counter}XRPYX"
        placeholders[key] = token
        out_parts.append(key)
        counter += 1
        last = end
    out_parts.append(text[last:])
    protected = ''.join(out_parts)

    return protected, placeholders


def restore_renpy_syntax(text: str, placeholders: Dict[str, str]) -> str:
    """Placeholder'ları orijinal değerleriyle değiştirir."""
    result = text
    for placeholder, original in placeholders.items():
        result = result.replace(placeholder, original)
    return result


class TranslationEngine(Enum):
    GOOGLE = "google"
    DEEPL = "deepl"
    PSEUDO = "pseudo"  # Pseudo-localization for UI testing


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
    text_type: Optional[str] = None  # Type of text: 'paragraph', 'dialogue', etc.


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
    """Multi-endpoint Google Translator with Lingva fallback.
    
    Uses multiple Google mirrors in parallel for faster translation,
    with Lingva Translate as a free fallback when Google fails.
    """
    
    # Multiple Google endpoints for parallel requests
    google_endpoints = [
        "https://translate.googleapis.com/translate_a/single",
        "https://translate.google.com/translate_a/single",
        "https://translate.google.com.tr/translate_a/single",
        "https://translate.google.co.uk/translate_a/single",
        "https://translate.google.de/translate_a/single",
        "https://translate.google.fr/translate_a/single",
        "https://translate.google.ru/translate_a/single",
        "https://translate.google.jp/translate_a/single",
        "https://translate.google.ca/translate_a/single",
        "https://translate.google.com.au/translate_a/single",
        "https://translate.google.pl/translate_a/single",
        "https://translate.google.es/translate_a/single",
        "https://translate.google.it/translate_a/single",
        # Gerekirse aşağıdaki satırları silebilirsiniz
    ]
    
    # Lingva instances (free, no API key needed)
    lingva_instances = [
        "https://lingva.ml",
        "https://lingva.lunar.icu",
        "https://lingva.garudalinux.org",  # Extra fallback; avoids AV warnings seen with plausibility.cloud
    ]
    
    # Default values (can be overridden from config)
    multi_q_concurrency = 16  # Paralel endpoint istekleri
    max_slice_chars = 3000   # Bir istekteki maksimum karakter
    max_texts_per_slice = 25  # Maximum texts per slice
    use_multi_endpoint = True  # Çoklu endpoint kullan
    enable_lingva_fallback = True  # Lingva fallback aktif

    def __init__(self, *args, config_manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._endpoint_index = 0
        self._lingva_index = 0
        self._endpoint_failures: Dict[str, int] = {}  # Track failures per endpoint

        # Load settings from config if available
        if config_manager:
            ts = config_manager.translation_settings
            self.use_multi_endpoint = getattr(ts, 'use_multi_endpoint', True)
            self.enable_lingva_fallback = getattr(ts, 'enable_lingva_fallback', True)
            self.multi_q_concurrency = getattr(ts, 'endpoint_concurrency', 16)
            self.max_slice_chars = getattr(ts, 'max_chars_per_request', 5000)
            self.max_texts_per_slice = getattr(ts, 'max_texts_per_slice', 25)
        # Keep a baseline to restore when proxy adaptasyonu devre dışı
        self._base_multi_q_concurrency = self.multi_q_concurrency
    
    def _get_next_endpoint(self) -> str:
        """Round-robin endpoint selection with failure tracking."""
        # Find endpoint with least failures
        min_failures = min(self._endpoint_failures.get(ep, 0) for ep in self.google_endpoints)
        available = [ep for ep in self.google_endpoints 
                     if self._endpoint_failures.get(ep, 0) <= min_failures + 2]
        
        if not available:
            # Reset failures if all endpoints are bad
            self._endpoint_failures.clear()
            available = self.google_endpoints
        
        self._endpoint_index = (self._endpoint_index + 1) % len(available)
        return available[self._endpoint_index]
    
    def _get_next_lingva(self) -> str:
        """Round-robin Lingva instance selection."""
        self._lingva_index = (self._lingva_index + 1) % len(self.lingva_instances)
        return self.lingva_instances[self._lingva_index]
    
    async def _translate_via_lingva(self, text: str, source: str, target: str) -> Optional[str]:
        """Translate using Lingva (free Google proxy, no API key)."""
        # Lingva uses different language codes
        lingva_source = source if source != 'auto' else 'auto'
        
        for _ in range(len(self.lingva_instances)):
            instance = self._get_next_lingva()
            url = f"{instance}/api/v1/{lingva_source}/{target}/{urllib.parse.quote(text)}"
            
            try:
                session = await self._get_session()
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and 'translation' in data:
                            return data['translation']
            except Exception as e:
                self.logger.debug(f"Lingva {instance} failed: {e}")
                continue
        
        return None

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Translate single text with multi-endpoint + Lingva fallback."""
        
        # Ren'Py değişkenlerini ve tag'lerini koru
        protected_text, placeholders = protect_renpy_syntax(request.text)
        
        params = {'client':'gtx','sl':request.source_lang,'tl':request.target_lang,'dt':'t','q':protected_text}
        
        # Try Google endpoints first (parallel race)
        async def try_endpoint(endpoint: str) -> Optional[str]:
            try:
                query = urllib.parse.urlencode(params, doseq=True, safe='')
                url = f"{endpoint}?{query}"
                session = await self._get_session()
                
                proxy = None
                if self.use_proxy and self.proxy_manager:
                    p = self.proxy_manager.get_next_proxy()
                    if p:
                        proxy = p.url
                
                async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if data and isinstance(data, list) and data[0]:
                            text = ''.join(part[0] for part in data[0] if part and part[0])
                            # Reset failure count on success
                            self._endpoint_failures[endpoint] = 0
                            return text
                    # Track failure
                    self._endpoint_failures[endpoint] = self._endpoint_failures.get(endpoint, 0) + 1
            except Exception:
                self._endpoint_failures[endpoint] = self._endpoint_failures.get(endpoint, 0) + 1
            return None
        
        translated_text = None
        
        # Multi-endpoint mode: Try 2 endpoints in parallel (fastest wins)
        if self.use_multi_endpoint:
            endpoints_to_try = [self._get_next_endpoint(), self._get_next_endpoint()]
            tasks = [asyncio.create_task(try_endpoint(ep)) for ep in endpoints_to_try]
            
            # Wait for first successful result
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    # Cancel remaining tasks
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    # Ren'Py değişkenlerini geri koy
                    final_text = restore_renpy_syntax(result, placeholders)
                    return TranslationResult(
                        request.text, final_text, request.source_lang, request.target_lang,
                        TranslationEngine.GOOGLE, True, confidence=0.9, metadata=request.metadata
                    )
        else:
            # Single endpoint mode
            result = await try_endpoint(self._get_next_endpoint())
            if result:
                # Ren'Py değişkenlerini geri koy
                final_text = restore_renpy_syntax(result, placeholders)
                return TranslationResult(
                    request.text, final_text, request.source_lang, request.target_lang,
                    TranslationEngine.GOOGLE, True, confidence=0.9, metadata=request.metadata
                )
        
        # All Google endpoints failed, try Lingva fallback (if enabled)
        if self.enable_lingva_fallback:
            self.logger.debug("Google endpoints failed, trying Lingva fallback...")
            lingva_result = await self._translate_via_lingva(
                protected_text, request.source_lang, request.target_lang
            )
            
            if lingva_result:
                # Ren'Py değişkenlerini geri koy
                final_text = restore_renpy_syntax(lingva_result, placeholders)
                return TranslationResult(
                    request.text, final_text, request.source_lang, request.target_lang,
                    TranslationEngine.GOOGLE, True, confidence=0.85, metadata=request.metadata
                )
        
        # Last resort: sync requests library
        try:
            import requests as req_lib
            def do():
                return req_lib.get(
                    self.google_endpoints[0], 
                    params=params, 
                    timeout=5, 
                    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
            resp = await asyncio.to_thread(do)
            if resp.status_code == 200:
                data2 = resp.json()
                if data2 and isinstance(data2, list) and data2[0]:
                    text = ''.join(part[0] for part in data2[0] if part and part[0])
                    # Ren'Py değişkenlerini geri koy
                    final_text = restore_renpy_syntax(text, placeholders)
                    return TranslationResult(
                        request.text, final_text, request.source_lang, request.target_lang,
                        TranslationEngine.GOOGLE, True, confidence=0.8, metadata=request.metadata
                    )
        except Exception as e:
            pass
        
        return TranslationResult(
            request.text, "", request.source_lang, request.target_lang,
            TranslationEngine.GOOGLE, False, "All translation methods failed", metadata=request.metadata
        )

    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Optimize edilmiş toplu çeviri:
        1. Aynı metinleri tek sefer çevir (dedup)
        2. Büyük listeyi karakter limitine göre slice'lara böl
        3. Slice'ları paralel (bounded) multi-q istekleriyle çalıştır
        4. Orijinal sıra korunur
        """
        if not requests:
            return []

        # Apply adaptive concurrency only when proxy kullanımda ve havuz var
        try:
            if (
                hasattr(self, 'proxy_manager') and self.proxy_manager
                and getattr(self, 'use_proxy', False)
                and getattr(self.proxy_manager, 'proxies', None)
            ):
                adaptive = self.proxy_manager.get_adaptive_concurrency()
                adaptive = max(2, min(adaptive, 64))
                self.logger.debug(f"Adaptive concurrency applied: {adaptive}")
                self.multi_q_concurrency = adaptive
            else:
                # Proxy yoksa başlangıç değerine dön
                base = getattr(self, '_base_multi_q_concurrency', None)
                if base:
                    self.multi_q_concurrency = base
        except Exception:
            pass
        
        self.logger.info(f"Starting batch translation: {len(requests)} texts, max_slice_chars={self.max_slice_chars}, concurrency={self.multi_q_concurrency}")
        
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

        # Slice oluştur (karakter limiti + metin sayısı limiti)
        slices: List[List[Tuple[int, TranslationRequest]]] = []
        cur: List[Tuple[int, TranslationRequest]] = []
        cur_chars = 0
        for item in unique_list:
            text_len = len(item[1].text)
            # Hem karakter hem metin sayısı limitini kontrol et
            if cur and (cur_chars + text_len > self.max_slice_chars or len(cur) >= self.max_texts_per_slice):
                slices.append(cur)
                cur = []
                cur_chars = 0
            cur.append(item)
            cur_chars += text_len
        if cur:
            slices.append(cur)
        
        self.logger.info(f"Dedup: {len(requests)} -> {len(unique_list)} unique, {len(slices)} slices")

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

    # Separator for batch translation
    # Using a unique pattern that translation engines are unlikely to modify
    # Numbers and specific pattern make it very unlikely to be translated
    BATCH_SEPARATOR = "\n|||RNLSEP999|||\n"
    
    # Alternative separators to try if first fails
    BATCH_SEPARATORS = [
        "\n|||RNLSEP999|||\n",
        "\n[[[SEP777]]]\n", 
        "\n###TXTSEP###\n",
    ]
    
    async def _multi_q(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        """Batch translation - tries separator method first, falls back to parallel individual.

        For better performance, uses parallel individual translation when batch method fails.
        """
        if not batch:
            return []
        if len(batch) == 1:
            return [await self.translate_single(batch[0])]

        total_chars = sum(len(r.text) for r in batch)

        # Küçük batch'ler için separator dene (daha hızlı)
        if len(batch) <= 25 and total_chars <= 4000:
            result = await self._try_batch_separator(batch)
            if result:
                return result

        # Separator başarısız veya batch büyük - paralel çeviri
        self.logger.debug(f"Using parallel translation for {len(batch)} texts")
        return await self._translate_parallel(batch)
    
    async def _try_batch_separator(self, batch: List[TranslationRequest]) -> Optional[List[TranslationResult]]:
        """Try batch translation with separator. Returns None if fails."""
        combined_text = self.BATCH_SEPARATOR.join(r.text for r in batch)
        
        params = {
            'client': 'gtx',
            'sl': batch[0].source_lang,
            'tl': batch[0].target_lang,
            'dt': 't',
            'q': combined_text
        }
        query = urllib.parse.urlencode(params)
        
        async def try_endpoint(endpoint: str) -> Optional[List[str]]:
            """Try a single endpoint, return list of translations or None."""
            try:
                url = f"{endpoint}?{query}"
                session = await self._get_session()
                
                proxy = None
                if self.use_proxy and self.proxy_manager:
                    p = self.proxy_manager.get_next_proxy()
                    if p:
                        proxy = p.url
                
                async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        self._endpoint_failures[endpoint] = self._endpoint_failures.get(endpoint, 0) + 1
                        self.logger.debug(f"Batch-sep {endpoint}: HTTP {resp.status}")
                        return None
                    
                    data = await resp.json(content_type=None)
                    segs = data[0] if isinstance(data, list) and data else None
                    if not segs:
                        self.logger.debug(f"Batch-sep {endpoint}: No segments in response")
                        return None
                    
                    # Combine all translation segments
                    full_translation = ""
                    for seg in segs:
                        if seg and seg[0]:
                            full_translation += seg[0]
                    
                    # Split by separator
                    parts = full_translation.split(self.BATCH_SEPARATOR)
                    
                    # Verify count matches
                    if len(parts) != len(batch):
                        self.logger.debug(f"Batch-sep {endpoint}: Part count mismatch - expected {len(batch)}, got {len(parts)}")
                        return None
                    
                    # Success - reset endpoint failures
                    self._endpoint_failures[endpoint] = 0
                    return parts
            
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._endpoint_failures[endpoint] = self._endpoint_failures.get(endpoint, 0) + 1
                self.logger.debug(f"Batch-sep failed on {endpoint}: {e}")
                return None
        
        # Parallel endpoint racing (if enabled)
        if self.use_multi_endpoint:
            endpoints_to_try = [self._get_next_endpoint() for _ in range(min(3, len(self.google_endpoints)))]
            tasks = [asyncio.create_task(try_endpoint(ep)) for ep in endpoints_to_try]
            
            try:
                # Wait for first successful result
                for coro in asyncio.as_completed(tasks):
                    try:
                        result = await coro
                        if result:
                            # Cancel remaining tasks
                            for t in tasks:
                                if not t.done():
                                    t.cancel()
                            self.logger.debug(f"Batch-sep success: {len(batch)} texts translated")
                            return [
                                TranslationResult(
                                    original_text=r.text,
                                    translated_text=t.strip(),
                                    source_lang=r.source_lang,
                                    target_lang=r.target_lang,
                                    engine=TranslationEngine.GOOGLE,
                                    success=True,
                                    confidence=0.9,
                                    metadata=r.metadata
                                )
                                for r, t in zip(batch, result)
                            ]
                    except asyncio.CancelledError:
                        raise
                # Avoid spamming user console; keep detailed info in debug logs only
                self.logger.debug(f"Batch-sep: All Google endpoints failed for {len(batch)} texts")
            except asyncio.CancelledError:
                # Cancel all tasks on cancellation
                for t in tasks:
                    if not t.done():
                        t.cancel()
                raise
        else:
            # Single endpoint mode (sequential)
            for _ in range(3):
                result = await try_endpoint(self._get_next_endpoint())
                if result:
                    return [
                        TranslationResult(
                            original_text=r.text,
                            translated_text=t.strip(),
                            source_lang=r.source_lang,
                            target_lang=r.target_lang,
                            engine=TranslationEngine.GOOGLE,
                            success=True,
                            confidence=0.9,
                            metadata=r.metadata
                        )
                        for r, t in zip(batch, result)
                    ]
                result = await try_endpoint(self._get_next_endpoint())
                if result:
                    return [
                        TranslationResult(
                            original_text=r.text,
                            translated_text=t,
                            source_lang=r.source_lang,
                            target_lang=r.target_lang,
                            engine=TranslationEngine.GOOGLE,
                            success=True,
                            confidence=0.9,
                            metadata=r.metadata
                        )
                        for r, t in zip(batch, result)
                    ]
        
        # Batch separator failed
        return None
    
    async def _translate_parallel(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        """Translate texts in parallel using multiple endpoints for speed."""
        if not batch:
            return []
        
        # Paralel çeviri için semaphore (aynı anda çok fazla istek atmamak için)
        sem = asyncio.Semaphore(self.multi_q_concurrency)
        
        async def translate_one(req: TranslationRequest) -> TranslationResult:
            async with sem:
                return await self.translate_single(req)
        
        # Tüm çevirileri paralel başlat
        tasks = [asyncio.create_task(translate_one(req)) for req in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sonuçları işle
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.debug(f"Parallel translation failed for text {i+1}: {result}")
                final_results.append(TranslationResult(
                    batch[i].text, "", batch[i].source_lang, batch[i].target_lang,
                    TranslationEngine.GOOGLE, False, str(result)
                ))
            else:
                final_results.append(result)
        
        success_count = sum(1 for r in final_results if r.success)
        self.logger.debug(f"Parallel translation: {success_count}/{len(batch)} successful")
        
        return final_results
    
    async def _translate_individually(self, batch: List[TranslationRequest]) -> List[TranslationResult]:
        """Translate texts one by one as fallback."""
        results = []
        for i, req in enumerate(batch):
            try:
                result = await self.translate_single(req)
                results.append(result)
                # Rate limiting - small delay between requests
                if i < len(batch) - 1:
                    await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.debug(f"Individual translation failed for text {i+1}: {e}")
                results.append(TranslationResult(
                    req.text, "", req.source_lang, req.target_lang,
                    TranslationEngine.GOOGLE, False, str(e)
                ))
            
            # Log progress every 10 texts
            if (i + 1) % 10 == 0:
                self.logger.debug(f"Individual translation progress: {i+1}/{len(batch)}")
        
        return results

    def get_supported_languages(self) -> Dict[str,str]:
        return {'auto':'Auto','en':'English','tr':'Turkish'}


class PseudoTranslator(BaseTranslator):
    """
    Pseudo-Localization Engine for testing UI bounds and font compatibility.
    
    This translator doesn't call any API - it transforms text locally to help:
    1. Test UI text overflow (adds expansion markers)
    2. Test font compatibility (uses accented characters)
    3. Identify untranslated strings (wrapped markers are visible)
    
    Modes:
    - 'expand': Adds [!!! ... !!!] markers for length testing
    - 'accent': Replaces vowels with accented versions
    - 'both': Combines expansion and accenting (default)
    """
    
    # Vowel accent mapping for pseudo-localization
    ACCENT_MAP = str.maketrans(
        "aeiouAEIOUyY",
        "àéîõüÀÉÎÕÜýÝ"
    )
    
    # Extended accent map for more thorough testing
    EXTENDED_ACCENT_MAP = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "àḃċḋéḟġḣíjḳĺṁńöṗqŕśṫûṿẁẍÿźÀḂĊḊÉḞĠḢÍJḲĹṀŃÖṖQŔŚṪÛṾẀẌŸŹ"
    )
    
    def __init__(self, *args, mode: str = "both", **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = mode  # 'expand', 'accent', or 'both'
    
    def _apply_accents(self, text: str) -> str:
        """Replace ASCII letters with accented versions."""
        return text.translate(self.ACCENT_MAP)
    
    def _apply_expansion(self, text: str) -> str:
        """Add expansion markers to test UI bounds."""
        # ~30% expansion typical for EN->DE/FR, simulate this
        return f"[!!! {text} !!!]"
    
    def _pseudo_transform(self, text: str) -> str:
        """
        Transform text based on mode:
        - expand: [!!! text !!!]
        - accent: tëxt wïth àccénts
        - both: [!!! tëxt wïth àccénts !!!]
        """
        if not text or not text.strip():
            return text
        
        result = text
        
        if self.mode in ('accent', 'both'):
            result = self._apply_accents(result)
        
        if self.mode in ('expand', 'both'):
            result = self._apply_expansion(result)
        
        return result
    
    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        """Pseudo-translate a single text (no API call)."""
        # Protect Ren'Py syntax before transformation
        protected_text, placeholders = protect_renpy_syntax(request.text)
        
        # Split by placeholders (both Ren'Py and Glossary ones)
        # Pattern matches XRPYX...XRPYX
        parts = re.split(r'(XRPYX[A-Z0-9]+XRPYX)', protected_text)
        new_parts = []
        for part in parts:
            if part.startswith('XRPYX') and part.endswith('XRPYX'):
                # It's a placeholder, keep it as is
                new_parts.append(part)
            else:
                # Translatable text, apply pseudo-transformation
                new_parts.append(self._pseudo_transform(part))
        
        pseudo_text = "".join(new_parts)
        
        # Restore Ren'Py syntax
        final_text = restore_renpy_syntax(pseudo_text, placeholders)
        
        return TranslationResult(
            original_text=request.text,
            translated_text=final_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            engine=TranslationEngine.PSEUDO,
            success=True,
            confidence=1.0,  # Always succeeds
            metadata={**request.metadata, 'pseudo_mode': self.mode}
        )
    
    async def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """Pseudo-translate a batch (all local, very fast)."""
        return [await self.translate_single(r) for r in requests]
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Pseudo-localization works for any language."""
        return {
            'pseudo': 'Pseudo-Localization (Test)',
            'expand': 'Expansion Test [!!! !!!]',
            'accent': 'Accent Test (àccénts)',
        }


class DeepLTranslator(BaseTranslator):
    base_url_paid = "https://api.deepl.com/v2/translate"
    base_url_free = "https://api-free.deepl.com/v2/translate"

    async def translate_single(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, "DeepL API key required")

        # DeepL is sensitive to special markers; protect Ren'Py placeholders
        protected_text, placeholders = protect_renpy_syntax(request.text)

        target_lang = request.target_lang.upper()
        data = {
            "auth_key": self.api_key,
            "text": protected_text,
            "target_lang": target_lang,
        }
        if request.source_lang and request.source_lang.lower() != "auto":
            data["source_lang"] = request.source_lang.upper()

        base_url = self.base_url_free if ":fx" in self.api_key or self.api_key.startswith("free:") else self.base_url_paid

        try:
            session = await self._get_session()
            proxy = None
            if self.use_proxy and self.proxy_manager:
                p = self.proxy_manager.get_next_proxy()
                if p:
                    proxy = p.url

            async with session.post(base_url, data=data, proxy=proxy, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, f"HTTP {resp.status}")

                payload = await resp.json(content_type=None)
                translations = payload.get("translations") if isinstance(payload, dict) else None
                if not translations:
                    return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, "No translations in response")

                translated = translations[0].get("text", "") if isinstance(translations[0], dict) else ""
                final_text = restore_renpy_syntax(translated, placeholders)

                return TranslationResult(request.text, final_text, request.source_lang, request.target_lang, TranslationEngine.DEEPL, True, confidence=0.9)
        except Exception as e:
            return TranslationResult(request.text, "", request.source_lang, request.target_lang, TranslationEngine.DEEPL, False, str(e))

    def get_supported_languages(self) -> Dict[str,str]:
        return {'en':'English','tr':'Turkish','de':'German','fr':'French','es':'Spanish','it':'Italian','pt':'Portuguese'}


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

    def set_concurrency_limit(self, limit: int):
        """Çeviri concurrency limitini dinamik olarak ayarla."""
        # Proxy tabanlı adaptif öneriyi TranslationManager seviyesinde uygulamak için
        # mevcut `set_max_concurrency` metodunu kullanıyoruz.
        try:
            self.set_max_concurrency(int(limit))
        except Exception:
            self.set_max_concurrency(max(1, int(limit)))
