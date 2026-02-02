"""
Handler for converting inner tags to numbered placeholders and back.

Inner tags are any tags (block or inline) found within a translation target element.
They are replaced with numbered placeholders during extraction and restored during insertion.

Placeholder format: {{n}} for opening, {{/n}} for closing, {{n/}} for self-closing
This format is chosen to:
1. Avoid confusion with HTML tags (GPT might alter <1> thinking it's HTML)
2. Use familiar template syntax that GPT recognizes and preserves
3. Allow flexible parsing for GPT errors (spaces, alternate slashes, etc.)

Example:
    <p>Hello <b>world</b> and <a href="x">link</a>!</p>

    After extraction:
        tagged_text: "Hello {{1}}world{{/1}} and {{2}}link{{/2}}!"
        inner_tags: [
            InnerTag(index=1, tag_name="b", attributes={}),
            InnerTag(index=2, tag_name="a", attributes={"href": "x"})
        ]

    After translation:
        translated: "안녕 {{1}}세상{{/1}} 그리고 {{2}}링크{{/2}}!"

    After restoration:
        <p>안녕 <b>세상</b> 그리고 <a href="x">링크</a>!</p>
"""

import logging
import re
from dataclasses import dataclass, field

from lxml import etree

from .constants import UNTRANSLATABLE_TAGS
from .models import InnerTag


# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

SELF_CLOSING_TAGS = frozenset({
    "br", "hr", "img", "input", "meta", "link",
    "area", "base", "col", "embed", "param",
    "source", "track", "wbr",
})
"""HTML/XHTML self-closing tags."""


# =============================================================================
# Regex Patterns for Parsing Placeholders
# =============================================================================

# Normalize broken brace placeholders before processing.
# Matches {{n} (missing closing) and {n}} (missing opening), but NOT {n}.
_BROKEN_BRACE_PATTERN = re.compile(
    r'\{\{\s*[/\\／]?\s*\d+\s*[/\\／]?\s*\}(?!\})'   # {{n} — missing closing brace
    r'|'
    r'(?<!\{)\{\s*[/\\／]?\s*\d+\s*[/\\／]?\s*\}\}'   # {n}} — missing opening brace
)

# Standard placeholder pattern (after normalization, all braces are doubled).
# Group 1: closing prefix (/, \, ／) or None
# Group 2: tag number (digits only)
# Group 3: self-closing suffix (/, \, ／) or None
#
# Handles GPT formatting errors:
# - Extra spaces: {{ 1 }}, {{ / 1 }}
# - Fullwidth slash: {{／1}}, {{1／}}
# - Backslash: {{\1}}, {{1\}}
#
# Note: Non-numeric content like {{name}} is NOT matched and preserved as-is.
TOKEN_PATTERN = re.compile(
    r'\{\{\s*([/\\／])?\s*(\d+)\s*([/\\／])?\s*\}\}'
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExtractionOutput:
    """Result of extracting inner tags from an element."""

    tagged_text: str
    inner_tags: list[InnerTag] = field(default_factory=list)


# =============================================================================
# InnerTagHandler
# =============================================================================

class InnerTagHandler:
    """
    Handles conversion between inner tags and numbered placeholders.

    Thread-safe: each method call is independent.
    """

    # -------------------------------------------------------------------------
    # Extraction
    # -------------------------------------------------------------------------

    def extract(self, element: etree._Element) -> ExtractionOutput:
        """
        Extract inner tags from an element and replace with numbered placeholders.

        Opaque tags (code, math, svg, etc.) are preserved as raw XML and treated
        as self-closing placeholders to avoid altering their internal structure.

        Args:
            element: The lxml element to process.

        Returns:
            ExtractionOutput with tagged_text and inner_tags list.
        """
        inner_tags: list[InnerTag] = []
        index_counter = [0]  # Mutable container for closure

        def process_node(node: etree._Element) -> str:
            """Recursively process a node and its children."""
            parts: list[str] = []

            if node.text:
                parts.append(node.text)

            for child in node:
                index_counter[0] += 1
                idx = index_counter[0]

                inner_tag = self._create_inner_tag(child, idx)
                inner_tags.append(inner_tag)

                # Opaque tags are treated as self-closing (no internal processing)
                if inner_tag.raw_xml is not None:
                    placeholder = f"{{{{{idx}/}}}}"  # {{n/}}
                else:
                    placeholder = self._format_placeholder(
                        idx,
                        inner_tag.is_self_closing,
                        inner_content=process_node(child) if not inner_tag.is_self_closing else None,
                    )
                parts.append(placeholder)

                if child.tail:
                    parts.append(child.tail)

            return "".join(parts)

        tagged_text = process_node(element)

        return ExtractionOutput(
            tagged_text=tagged_text,
            inner_tags=inner_tags,
        )

    def _create_inner_tag(self, element: etree._Element, index: int) -> InnerTag:
        """
        Create an InnerTag from an lxml element.

        For opaque tags (code, math, svg, etc.), the raw XML is preserved
        to maintain internal structure without modification.

        Args:
            element: The lxml element.
            index: The placeholder index.

        Returns:
            InnerTag with metadata extracted from the element.
        """
        tag_name = (
            etree.QName(element.tag).localname
            if isinstance(element.tag, str)
            else str(element.tag)
        )

        # Check if this is an opaque tag that should be preserved as-is
        is_opaque = tag_name.lower() in UNTRANSLATABLE_TAGS
        raw_xml: str | None = None

        if is_opaque:
            # Preserve the entire element as raw XML
            raw_xml = etree.tostring(element, encoding="unicode")

        # Collect attributes (excluding namespace declarations)
        attributes = {
            k: v for k, v in element.attrib.items()
            if not k.startswith("{") and not k.startswith("xmlns")
        }

        is_self_closing = tag_name.lower() in SELF_CLOSING_TAGS

        return InnerTag(
            index=index,
            tag_name=tag_name,
            attributes=attributes,
            is_self_closing=is_self_closing,
            raw_xml=raw_xml,
        )

    def _format_placeholder(
        self,
        index: int,
        is_self_closing: bool,
        inner_content: str | None = None,
    ) -> str:
        """
        Format a placeholder string.

        Args:
            index: The placeholder index.
            is_self_closing: Whether the tag is self-closing.
            inner_content: Content between opening and closing tags (for paired tags).

        Returns:
            Formatted placeholder string.
        """
        if is_self_closing:
            return f"{{{{{index}/}}}}"  # {{n/}}
        else:
            return f"{{{{{index}}}}}{inner_content or ''}{{{{/{index}}}}}"  # {{n}}...{{/n}}

    # -------------------------------------------------------------------------
    # Restoration
    # -------------------------------------------------------------------------

    def restore(
        self,
        translated_text: str,
        inner_tags: list[InnerTag],
        nsmap: dict[str | None, str] | None = None,
    ) -> str:
        """
        Restore numbered placeholders back to original tags.

        Handles various GPT formatting errors:
        - Extra spaces: {{ 1 }}, {{ / 1 }}
        - Alternate slashes: {{／1}}, {{1／}}
        - Backslashes: {{\\1}}, {{1\\}}

        Unknown placeholder indices (not in inner_tags) are removed with a warning log.
        Non-numeric placeholders like {{name}} are preserved as-is.

        Args:
            translated_text: Text with numbered placeholders (e.g., "{{1}}text{{/1}}")
            inner_tags: List of InnerTag metadata for restoration
            nsmap: Optional namespace map for the output XML (unused, for API compatibility)

        Returns:
            XML string with original tags restored (without root element wrapper).
        """
        if not inner_tags:
            return translated_text

        tag_map = {tag.index: tag for tag in inner_tags}
        result_parts: list[str] = []
        tag_stack: list[int] = []
        last_index = 0

        for match in TOKEN_PATTERN.finditer(translated_text):
            closing_prefix = match.group(1)
            tag_num = int(match.group(2))
            self_closing_suffix = match.group(3)
            start, end = match.span()

            # Add text before this tag
            if start > last_index:
                result_parts.append(translated_text[last_index:start])

            tag = tag_map.get(tag_num)
            restored = self._restore_single_tag(
                tag=tag,
                tag_num=tag_num,
                closing_prefix=closing_prefix,
                self_closing_suffix=self_closing_suffix,
                tag_stack=tag_stack,
                original_placeholder=match.group(0),
            )
            result_parts.append(restored)

            last_index = end

        # Add remaining text after last tag
        if last_index < len(translated_text):
            result_parts.append(translated_text[last_index:])

        return "".join(result_parts)

    def _restore_single_tag(
        self,
        tag: InnerTag | None,
        tag_num: int,
        closing_prefix: str | None,
        self_closing_suffix: str | None,
        tag_stack: list[int],
        original_placeholder: str,
    ) -> str:
        """
        Restore a single placeholder to its original tag.

        Args:
            tag: The InnerTag metadata (or None if unknown).
            tag_num: The placeholder number.
            closing_prefix: Slash prefix if this is a closing tag.
            self_closing_suffix: Slash suffix if this is a self-closing tag.
            tag_stack: Stack tracking opened tags (modified in-place).
            original_placeholder: The original matched placeholder string (for logging).

        Returns:
            Restored XML tag string, or empty string if tag is unknown.
        """
        # Unknown tag index - log warning and remove
        if tag is None:
            logger.warning(
                "Unknown placeholder index %d encountered: '%s'. Removing from output.",
                tag_num,
                original_placeholder,
            )
            return ""

        # Opaque tag with raw XML - return as-is
        if tag.raw_xml is not None:
            return tag.raw_xml

        if self_closing_suffix and not closing_prefix:
            # Self-closing: {{n/}}
            attr_str = self._build_attr_string(tag.attributes)
            return f"<{tag.tag_name}{attr_str}/>"

        elif closing_prefix:
            # Closing tag: {{/n}}
            if tag_stack and tag_stack[-1] == tag_num:
                tag_stack.pop()
            return f"</{tag.tag_name}>"

        else:
            # Opening tag: {{n}}
            attr_str = self._build_attr_string(tag.attributes)
            if tag.is_self_closing:
                return f"<{tag.tag_name}{attr_str}/>"
            tag_stack.append(tag_num)
            return f"<{tag.tag_name}{attr_str}>"

    def _build_attr_string(self, attributes: dict[str, str]) -> str:
        """
        Build attribute string for an XML tag.

        Args:
            attributes: Dictionary of attribute name-value pairs.

        Returns:
            Formatted attribute string (with leading space if non-empty).
        """
        if not attributes:
            return ""
        attr_parts = [f'{k}="{v}"' for k, v in attributes.items()]
        return " " + " ".join(attr_parts)

    # -------------------------------------------------------------------------
    # Restoration to Element
    # -------------------------------------------------------------------------

    def restore_to_element(
        self,
        parent_tag: str,
        translated_text: str,
        inner_tags: list[InnerTag],
        parent_attributes: dict[str, str] | None = None,
        nsmap: dict[str | None, str] | None = None,
    ) -> etree._Element:
        """
        Restore translated text with placeholders to an lxml Element.

        Args:
            parent_tag: Tag name for the parent element (e.g., "p", "div")
            translated_text: Text with numbered placeholders
            inner_tags: List of InnerTag metadata
            parent_attributes: Attributes for the parent element
            nsmap: Namespace map for the element

        Returns:
            lxml Element with restored structure.
        """
        normalized_text = self._normalize_placeholders(translated_text)
        cleaned_text = self._filter_invalid_placeholders(normalized_text, inner_tags)
        escaped_text = self._escape_text_outside_placeholders(cleaned_text)
        restored_xml = self.restore(escaped_text, inner_tags, nsmap)
        attr_str = self._build_attr_string(parent_attributes) if parent_attributes else ""
        full_xml = f"<{parent_tag}{attr_str}>{restored_xml}</{parent_tag}>"

        try:
            return etree.fromstring(full_xml.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            logger.warning(
                "XML parsing failed for restored content. Error: %s. Content: %s",
                e,
                restored_xml[:200] + "..." if len(restored_xml) > 200 else restored_xml,
            )
            raise

    def _normalize_placeholders(self, text: str) -> str:
        """
        Fix broken brace placeholders: {{n} → {{n}}, {n}} → {{n}}.

        Single-brace {n} is NOT affected (not matched by _BROKEN_BRACE_PATTERN).
        """
        def _fix_braces(m: re.Match) -> str:
            s = m.group(0)
            if s.startswith('{{'):
                return s + '}'   # {{n} → {{n}}
            return '{' + s       # {n}} → {{n}}

        return _BROKEN_BRACE_PATTERN.sub(_fix_braces, text)

    def _filter_invalid_placeholders(
        self,
        text: str,
        inner_tags: list[InnerTag],
    ) -> str:
        """
        Remove placeholders that don't have a valid matching pair.

        Rules:
        - Only top-of-stack closing tags are considered valid matches.
        - Unknown indices are removed.
        - Unmatched opening/closing placeholders are removed.
        """
        tag_map = {tag.index: tag for tag in inner_tags}
        matches: list[re.Match] = list(TOKEN_PATTERN.finditer(text))
        keep_flags = [False] * len(matches)
        stack: list[tuple[int, int]] = []

        for i, match in enumerate(matches):
            closing_prefix = match.group(1)
            tag_num = int(match.group(2))
            self_closing_suffix = match.group(3)

            if tag_num not in tag_map:
                continue

            if self_closing_suffix and not closing_prefix:
                keep_flags[i] = True
                continue

            if closing_prefix:
                if stack and stack[-1][0] == tag_num:
                    _, open_index = stack.pop()
                    keep_flags[open_index] = True
                    keep_flags[i] = True
                continue

            # Opening tag
            stack.append((tag_num, i))

        # Any openings left in the stack are unmatched; keep_flags stays False
        output_parts: list[str] = []
        last_index = 0
        for keep, match in zip(keep_flags, matches):
            start, end = match.span()
            if start > last_index:
                output_parts.append(text[last_index:start])
            if keep:
                output_parts.append(match.group(0))
            last_index = end

        if last_index < len(text):
            output_parts.append(text[last_index:])

        return "".join(output_parts)

    def _escape_text_outside_placeholders(self, text: str) -> str:
        """
        Escape XML special chars outside placeholders to avoid parser errors.
        """
        parts: list[str] = []
        last_index = 0
        for match in TOKEN_PATTERN.finditer(text):
            start, end = match.span()

            if start > last_index:
                parts.append(self._escape_xml_text(text[last_index:start]))
            parts.append(match.group(0))
            last_index = end

        if last_index < len(text):
            parts.append(self._escape_xml_text(text[last_index:]))

        return "".join(parts)

    def _escape_xml_text(self, text: str) -> str:
        """
        Escape &, <, > in text while preserving existing entities.
        """
        text = re.sub(r"&(?![a-zA-Z]+;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", text)
        return text.replace("<", "&lt;").replace(">", "&gt;")

    def _escape_xml_content(self, content: str) -> str:
        """
        Escape XML special characters in content.

        Args:
            content: The content to escape.

        Returns:
            Escaped content safe for XML.
        """
        return (
            content
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
