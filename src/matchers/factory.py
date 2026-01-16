"""
Factory for creating ElementMatcher instances.

Provides a centralized way to create matchers with a default strategy.
"""

from enum import Enum
from .base import ElementMatcher


class MatcherStrategy(Enum):
    """Available matcher strategies."""
    TEXT_EMERGENCE = "text_emergence"
    OUTER_CONTEXT = "outer_context"
    LEAF_BLOCK = "leaf_block"
    ALL_ELEMENTS = "all_elements"


class MatcherFactory:
    """Factory for creating ElementMatcher instances with caching."""

    _instances: dict[MatcherStrategy, ElementMatcher] = {}
    _default_strategy: MatcherStrategy = MatcherStrategy.ALL_ELEMENTS

    @classmethod
    def create(cls, strategy: MatcherStrategy | None = None) -> ElementMatcher:
        """
        Create or return a cached matcher instance.

        Args:
            strategy: The matcher strategy to use. Defaults to TEXT_EMERGENCE.

        Returns:
            An ElementMatcher instance.
        """
        if strategy is None:
            strategy = cls._default_strategy

        if strategy not in cls._instances:
            cls._instances[strategy] = cls._build(strategy)
        return cls._instances[strategy]

    @classmethod
    def _build(cls, strategy: MatcherStrategy) -> ElementMatcher:
        from .implementations import (
            TextEmergenceMatcher,
            OuterContextMatcher,
            LeafBlockMatcher,
            AllElementsMatcher,
        )

        match strategy:
            case MatcherStrategy.TEXT_EMERGENCE:
                return TextEmergenceMatcher()
            case MatcherStrategy.OUTER_CONTEXT:
                return OuterContextMatcher()
            case MatcherStrategy.LEAF_BLOCK:
                return LeafBlockMatcher()
            case MatcherStrategy.ALL_ELEMENTS:
                return AllElementsMatcher()
            case _:
                raise ValueError(f"Unknown strategy: {strategy}")
