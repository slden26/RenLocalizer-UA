"""Coverage / Diagnostic reporting for RenLocalizer pipeline.

Small helper to collect extraction/translation/save events and emit
a JSON report summarizing counts and per-file details.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class FileReport:
    file_path: str
    extracted: int = 0
    translated: int = 0
    written: int = 0
    skipped: int = 0
    unchanged: int = 0
    entries: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DiagnosticReport:
    project: str = ''
    target_language: str = ''
    total_extracted: int = 0
    total_translated: int = 0
    total_written: int = 0
    total_skipped: int = 0
    total_unchanged: int = 0
    files: Dict[str, FileReport] = field(default_factory=dict)

    def add_extracted(self, file_path: str, entry: Dict[str, Any]):
        fr = self.files.get(file_path)
        if not fr:
            fr = FileReport(file_path=file_path)
            self.files[file_path] = fr
        fr.extracted += 1
        rec = {**entry, 'status': 'extracted'}
        # include raw_text if available for ID/debug matching
        if 'raw_text' in entry and entry.get('raw_text') is not None:
            rec['raw_text'] = entry.get('raw_text')
        # If a translation_id is supplied or can be computed externally, include it.
        if 'translation_id' in entry and entry.get('translation_id'):
            rec['translation_id'] = entry.get('translation_id')
        fr.entries.append(rec)
        self.total_extracted += 1

    def mark_translated(self, file_path: str, translation_id: str, translated_text: str, original_text: str = None):
        fr = self.files.get(file_path)
        if not fr:
            fr = FileReport(file_path=file_path)
            self.files[file_path] = fr
        fr.translated += 1
        rec = {'translation_id': translation_id, 'translated_text': translated_text, 'status': 'translated'}
        if original_text is not None:
            rec['original_text'] = original_text
        fr.entries.append(rec)
        self.total_translated += 1

    def mark_written(self, file_path: str, translation_id: str):
        fr = self.files.get(file_path)
        if not fr:
            fr = FileReport(file_path=file_path)
            self.files[file_path] = fr
        fr.written += 1
        fr.entries.append({'translation_id': translation_id, 'status': 'written'})
        self.total_written += 1

    def mark_skipped(self, file_path: str, reason: str, entry: Dict[str, Any] = None):
        fr = self.files.get(file_path)
        if not fr:
            fr = FileReport(file_path=file_path)
            self.files[file_path] = fr
        fr.skipped += 1
        rec = {'status': 'skipped', 'reason': reason}
        if entry:
            rec.update(entry)
        fr.entries.append(rec)
        self.total_skipped += 1

    def mark_unchanged(self, file_path: str, translation_id: str, original_text: str = None):
        fr = self.files.get(file_path)
        if not fr:
            fr = FileReport(file_path=file_path)
            self.files[file_path] = fr
        fr.unchanged += 1
        rec = {'translation_id': translation_id, 'status': 'unchanged'}
        if original_text is not None:
            rec['original_text'] = original_text
        fr.entries.append(rec)
        self.total_unchanged += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'project': self.project,
            'target_language': self.target_language,
            'totals': {
                'extracted': self.total_extracted,
                'translated': self.total_translated,
                'written': self.total_written,
                'skipped': self.total_skipped,
                'unchanged': self.total_unchanged,
            },
            'files': {p: {
                'extracted': fr.extracted,
                'translated': fr.translated,
                'written': fr.written,
                'skipped': fr.skipped,
                'unchanged': fr.unchanged,
                'entries': fr.entries,
            } for p, fr in self.files.items()}
        }

    def write(self, path: str):
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
