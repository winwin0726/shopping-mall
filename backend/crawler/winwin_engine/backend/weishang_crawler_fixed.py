"""Compatibility wrapper for the current Weishang crawler implementation.

This module used to contain a large recovered copy of the crawler, but that
copy had encoding damage and syntax errors. Keep the legacy import path alive
while delegating to the maintained implementation under platforms/weishang.
"""

try:
    from backend.platforms.weishang.crawler import (
        GeminiProductSchema,
        WeishangCrawler,
        apply_forbidden_words,
        get_korean_initial,
        sanitize_path_component,
    )
except ImportError:
    from platforms.weishang.crawler import (
        GeminiProductSchema,
        WeishangCrawler,
        apply_forbidden_words,
        get_korean_initial,
        sanitize_path_component,
    )

__all__ = [
    "GeminiProductSchema",
    "WeishangCrawler",
    "apply_forbidden_words",
    "get_korean_initial",
    "sanitize_path_component",
]
