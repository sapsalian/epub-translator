"""
Element selectors for EPUB text processing.

Selectors determine which elements should be processed (e.g., translated).
"""

from .implementations import (
    TargetTagSelector,
    TextEmergenceSelector,
    PhrasingContentSelector,
)

__all__ = [
    "TargetTagSelector",
    "TextEmergenceSelector",
    "PhrasingContentSelector",
]
