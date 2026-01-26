"""
Constants for the translation pipeline.

Defines tags that should not be translated or should be preserved as-is.
"""

# Tags whose content should never be translated.
# Used by:
# - TranslatableElementFilter: Exclude elements with these ancestors
# - InnerTagHandler: Preserve these tags as raw XML when found inside translation targets
UNTRANSLATABLE_TAGS = frozenset({
    # Code and technical content
    "code",
    "pre",
    "script",
    "style",
    "kbd",
    "samp",
    "var",
    # Math and graphics (preserve structure)
    "math",
    "svg",
    # Metadata (typically in <head>, but included for completeness)
    "head",
    "meta",
    "link",
    "base",
    # Special purpose elements
    "template",
    "noscript",
    "iframe",
    "object",
    "embed",
})
