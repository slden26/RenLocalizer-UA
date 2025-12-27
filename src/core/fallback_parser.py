"""Optional pyparsing-based fallback extractor.

This module provides a lightweight extraction routine that is used only
when the main regex-based parser fails to extract anything. It depends on
`pyparsing` being installed; if it's not available the functions return
an empty list and do not raise.
"""
from typing import List, Dict



def parse_with_pyparsing(content: str, file_path: str = "") -> List[Dict]:
    """
    Regex tabanlı parser başarısız olursa, pyparsing grammar ile fallback extraction yapar.
    Hata durumunda loglama ile sessizce boş liste döner.
    """
    try:
        from src.core.pyparse_grammar import extract_with_pyparsing
        return extract_with_pyparsing(content, file_path)
    except Exception as e:
        # Hata loglama (geliştirici için)
        import logging
        logging.warning(f"Pyparsing fallback failed: {e}")
        return []
