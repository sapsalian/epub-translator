"""
Element matchers for EPUB text processing.

Matchers determine which elements should be processed (e.g., translated).
"""

from .implementations import (
    TargetTagMatcher,
    TextEmergenceMatcher,
    PhrasingContentMatcher,
)
from .base import ElementMatcher

__all__ = [
    "TargetTagMatcher",
    "TextEmergenceMatcher",
    "PhrasingContentMatcher",
    "ElementMatcher",
]
