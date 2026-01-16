"""
Element matchers for EPUB text processing.

Matchers determine which elements should be processed (e.g., translated).
"""

from .base import ElementMatcher
from .factory import MatcherFactory, MatcherStrategy

__all__ = [
    "ElementMatcher",
    "MatcherFactory",
    "MatcherStrategy",
]
