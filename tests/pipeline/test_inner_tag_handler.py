"""Tests for InnerTagHandler."""

import logging

import pytest
from lxml import etree

from src.pipeline.inner_tag_handler import InnerTagHandler, ExtractionOutput
from src.pipeline.models import InnerTag


@pytest.fixture
def handler() -> InnerTagHandler:
    return InnerTagHandler()


class TestExtract:
    """Tests for InnerTagHandler.extract()"""

    def test_plain_text_no_inner_tags(self, handler: InnerTagHandler):
        """Plain text without inner tags."""
        element = etree.fromstring("<p>Hello world</p>")
        result = handler.extract(element)

        assert result.tagged_text == "Hello world"
        assert result.inner_tags == []

    def test_single_inner_tag(self, handler: InnerTagHandler):
        """Single inner tag."""
        element = etree.fromstring("<p>Hello <b>world</b>!</p>")
        result = handler.extract(element)

        assert result.tagged_text == "Hello {{1}}world{{/1}}!"
        assert len(result.inner_tags) == 1
        assert result.inner_tags[0].index == 1
        assert result.inner_tags[0].tag_name == "b"
        assert result.inner_tags[0].attributes == {}
        assert result.inner_tags[0].is_self_closing is False

    def test_multiple_inner_tags(self, handler: InnerTagHandler):
        """Multiple inner tags at same level."""
        element = etree.fromstring("<p>Hello <b>world</b> and <i>universe</i>!</p>")
        result = handler.extract(element)

        assert result.tagged_text == "Hello {{1}}world{{/1}} and {{2}}universe{{/2}}!"
        assert len(result.inner_tags) == 2
        assert result.inner_tags[0].tag_name == "b"
        assert result.inner_tags[1].tag_name == "i"

    def test_nested_inner_tags(self, handler: InnerTagHandler):
        """Nested inner tags."""
        element = etree.fromstring("<p>Hello <b><i>world</i></b>!</p>")
        result = handler.extract(element)

        assert result.tagged_text == "Hello {{1}}{{2}}world{{/2}}{{/1}}!"
        assert len(result.inner_tags) == 2
        assert result.inner_tags[0].tag_name == "b"
        assert result.inner_tags[1].tag_name == "i"

    def test_tag_with_attributes(self, handler: InnerTagHandler):
        """Tag with attributes."""
        element = etree.fromstring('<p>Click <a href="https://example.com" class="link">here</a>!</p>')
        result = handler.extract(element)

        assert result.tagged_text == "Click {{1}}here{{/1}}!"
        assert len(result.inner_tags) == 1
        assert result.inner_tags[0].tag_name == "a"
        assert result.inner_tags[0].attributes == {"href": "https://example.com", "class": "link"}

    def test_self_closing_tag(self, handler: InnerTagHandler):
        """Self-closing tag like <br/>."""
        element = etree.fromstring("<p>Line 1<br/>Line 2</p>")
        result = handler.extract(element)

        assert result.tagged_text == "Line 1{{1/}}Line 2"
        assert len(result.inner_tags) == 1
        assert result.inner_tags[0].tag_name == "br"
        assert result.inner_tags[0].is_self_closing is True

    def test_mixed_self_closing_and_paired(self, handler: InnerTagHandler):
        """Mix of self-closing and paired tags."""
        element = etree.fromstring("<p>Hello<br/><b>world</b></p>")
        result = handler.extract(element)

        assert result.tagged_text == "Hello{{1/}}{{2}}world{{/2}}"
        assert len(result.inner_tags) == 2
        assert result.inner_tags[0].is_self_closing is True
        assert result.inner_tags[1].is_self_closing is False

    def test_img_tag_with_attributes(self, handler: InnerTagHandler):
        """Image tag with src attribute."""
        element = etree.fromstring('<p>See <img src="cat.png" alt="cat"/>!</p>')
        result = handler.extract(element)

        assert result.tagged_text == "See {{1/}}!"
        assert result.inner_tags[0].tag_name == "img"
        assert result.inner_tags[0].attributes == {"src": "cat.png", "alt": "cat"}
        assert result.inner_tags[0].is_self_closing is True

    def test_empty_inner_tag(self, handler: InnerTagHandler):
        """Empty inner tag with no content."""
        element = etree.fromstring("<p>Hello <span></span> world</p>")
        result = handler.extract(element)

        assert result.tagged_text == "Hello {{1}}{{/1}} world"
        assert result.inner_tags[0].tag_name == "span"

    def test_complex_nested_structure(self, handler: InnerTagHandler):
        """Complex nested structure."""
        element = etree.fromstring("<p>A <b>B <i>C</i> D</b> E <a href='x'>F</a> G</p>")
        result = handler.extract(element)

        assert result.tagged_text == "A {{1}}B {{2}}C{{/2}} D{{/1}} E {{3}}F{{/3}} G"
        assert len(result.inner_tags) == 3


class TestRestore:
    """Tests for InnerTagHandler.restore()"""

    def test_plain_text_no_placeholders(self, handler: InnerTagHandler):
        """Plain text without placeholders."""
        result = handler.restore("Hello world", [])
        assert result == "Hello world"

    def test_single_placeholder(self, handler: InnerTagHandler):
        """Single placeholder restoration."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{1}}world{{/1}}!", inner_tags)

        assert result == "Hello <b>world</b>!"

    def test_multiple_placeholders(self, handler: InnerTagHandler):
        """Multiple placeholders."""
        inner_tags = [
            InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False),
            InnerTag(index=2, tag_name="i", attributes={}, is_self_closing=False),
        ]
        result = handler.restore("Hello {{1}}world{{/1}} and {{2}}universe{{/2}}!", inner_tags)

        assert result == "Hello <b>world</b> and <i>universe</i>!"

    def test_nested_placeholders(self, handler: InnerTagHandler):
        """Nested placeholders."""
        inner_tags = [
            InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False),
            InnerTag(index=2, tag_name="i", attributes={}, is_self_closing=False),
        ]
        result = handler.restore("Hello {{1}}{{2}}world{{/2}}{{/1}}!", inner_tags)

        assert result == "Hello <b><i>world</i></b>!"

    def test_placeholder_with_attributes(self, handler: InnerTagHandler):
        """Placeholder with attributes."""
        inner_tags = [
            InnerTag(index=1, tag_name="a", attributes={"href": "https://example.com"}, is_self_closing=False)
        ]
        result = handler.restore("Click {{1}}here{{/1}}!", inner_tags)

        assert result == 'Click <a href="https://example.com">here</a>!'

    def test_self_closing_placeholder(self, handler: InnerTagHandler):
        """Self-closing placeholder."""
        inner_tags = [InnerTag(index=1, tag_name="br", attributes={}, is_self_closing=True)]
        result = handler.restore("Line 1{{1/}}Line 2", inner_tags)

        assert result == "Line 1<br/>Line 2"

    def test_unknown_placeholder_removed(self, handler: InnerTagHandler):
        """Unknown placeholder index is removed."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{1}}world{{/1}} {{2}}unknown{{/2}}!", inner_tags)

        # Unknown index 2 should be removed
        assert result == "Hello <b>world</b> unknown!"

    def test_non_numeric_placeholder_preserved(self, handler: InnerTagHandler):
        """Non-numeric placeholder like {{name}} is preserved as-is."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{1}}world{{/1}} and {{name}}!", inner_tags)

        # {{name}} should be preserved (not matched by regex)
        assert result == "Hello <b>world</b> and {{name}}!"

    def test_template_variables_preserved(self, handler: InnerTagHandler):
        """Template variables like {{user.name}} are preserved."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{1}}{{user.name}}{{/1}}!", inner_tags)

        assert result == "Hello <b>{{user.name}}</b>!"

    def test_translated_korean(self, handler: InnerTagHandler):
        """Korean translated text."""
        inner_tags = [
            InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False),
            InnerTag(index=2, tag_name="a", attributes={"href": "x"}, is_self_closing=False),
        ]
        result = handler.restore("안녕 {{1}}세상{{/1}} 그리고 {{2}}링크{{/2}}!", inner_tags)

        assert result == '안녕 <b>세상</b> 그리고 <a href="x">링크</a>!'


class TestRestoreWithGPTErrors:
    """Tests for handling GPT formatting errors in restore()"""

    def test_extra_spaces(self, handler: InnerTagHandler):
        """Handle extra spaces in placeholders."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{ 1 }}world{{ / 1 }}!", inner_tags)

        assert result == "Hello <b>world</b>!"

    def test_fullwidth_slash(self, handler: InnerTagHandler):
        """Handle fullwidth slash (／) in closing tags."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{1}}world{{／1}}!", inner_tags)

        assert result == "Hello <b>world</b>!"

    def test_backslash(self, handler: InnerTagHandler):
        """Handle backslash in closing tags."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        result = handler.restore("Hello {{1}}world{{\\1}}!", inner_tags)

        assert result == "Hello <b>world</b>!"

    def test_self_closing_with_fullwidth_slash(self, handler: InnerTagHandler):
        """Handle fullwidth slash in self-closing tags."""
        inner_tags = [InnerTag(index=1, tag_name="br", attributes={}, is_self_closing=True)]
        result = handler.restore("Line 1{{1／}}Line 2", inner_tags)

        assert result == "Line 1<br/>Line 2"

    def test_mixed_errors(self, handler: InnerTagHandler):
        """Handle mixed formatting errors."""
        inner_tags = [
            InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False),
            InnerTag(index=2, tag_name="i", attributes={}, is_self_closing=False),
        ]
        result = handler.restore("Hello {{ 1 }}world{{／1}} and {{2}}text{{ \\ 2 }}!", inner_tags)

        assert result == "Hello <b>world</b> and <i>text</i>!"


class TestRestoreToElement:
    """Tests for InnerTagHandler.restore_to_element()"""

    def test_simple_restoration(self, handler: InnerTagHandler):
        """Simple restoration to element."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]
        element = handler.restore_to_element("p", "Hello {{1}}world{{/1}}!", inner_tags)

        assert element.tag == "p"
        assert element.text == "Hello "
        assert element[0].tag == "b"
        assert element[0].text == "world"
        assert element[0].tail == "!"

    def test_with_parent_attributes(self, handler: InnerTagHandler):
        """Restoration with parent attributes."""
        inner_tags = []
        element = handler.restore_to_element(
            "p",
            "Hello world",
            inner_tags,
            parent_attributes={"class": "intro", "id": "para1"},
        )

        assert element.tag == "p"
        assert element.get("class") == "intro"
        assert element.get("id") == "para1"


class TestRoundTrip:
    """Round-trip tests: extract -> translate -> restore"""

    def test_simple_round_trip(self, handler: InnerTagHandler):
        """Simple round-trip."""
        original = "<p>Hello <b>world</b>!</p>"
        element = etree.fromstring(original)

        # Extract
        extracted = handler.extract(element)
        assert extracted.tagged_text == "Hello {{1}}world{{/1}}!"

        # Simulate translation (same text for this test)
        translated = extracted.tagged_text

        # Restore
        restored = handler.restore(translated, extracted.inner_tags)
        assert restored == "Hello <b>world</b>!"

    def test_complex_round_trip(self, handler: InnerTagHandler):
        """Complex round-trip with multiple tags."""
        original = '<p>Click <a href="url">here</a> or <b>press <i>enter</i></b>.</p>'
        element = etree.fromstring(original)

        # Extract
        extracted = handler.extract(element)

        # Simulate translation
        translated = "클릭 {{1}}여기{{/1}} 또는 {{2}}{{3}}엔터{{/3}}를 누르세요{{/2}}."

        # Restore
        restored = handler.restore(translated, extracted.inner_tags)

        # Verify structure
        assert '<a href="url">여기</a>' in restored
        assert "<b>" in restored
        assert "<i>엔터</i>" in restored

    def test_round_trip_preserves_attributes(self, handler: InnerTagHandler):
        """Round-trip preserves all attributes."""
        original = '<p>See <img src="cat.png" alt="A cat"/> and <a href="dog.html" target="_blank">dog</a>.</p>'
        element = etree.fromstring(original)

        extracted = handler.extract(element)
        restored = handler.restore(extracted.tagged_text, extracted.inner_tags)

        assert 'src="cat.png"' in restored
        assert 'alt="A cat"' in restored
        assert 'href="dog.html"' in restored
        assert 'target="_blank"' in restored

    def test_round_trip_with_gpt_errors(self, handler: InnerTagHandler):
        """Round-trip handles GPT formatting errors."""
        original = "<p>Hello <b>world</b>!</p>"
        element = etree.fromstring(original)

        # Extract
        extracted = handler.extract(element)

        # Simulate GPT returning with formatting errors
        translated_with_errors = "안녕 {{ 1 }}세상{{／1}}!"

        # Restore should handle errors
        restored = handler.restore(translated_with_errors, extracted.inner_tags)
        assert restored == "안녕 <b>세상</b>!"


class TestOpaqueTags:
    """Tests for opaque tag handling (code, math, svg, etc.)"""

    def test_code_tag_preserved_as_raw_xml(self, handler: InnerTagHandler):
        """Code tag content is preserved as raw XML."""
        element = etree.fromstring("<p>See <code>x = 1</code> example.</p>")
        result = handler.extract(element)

        assert result.tagged_text == "See {{1/}} example."
        assert len(result.inner_tags) == 1
        assert result.inner_tags[0].tag_name == "code"
        assert result.inner_tags[0].raw_xml is not None
        assert "x = 1" in result.inner_tags[0].raw_xml

    def test_math_tag_preserved_as_raw_xml(self, handler: InnerTagHandler):
        """Math tag structure is preserved as raw XML."""
        element = etree.fromstring(
            '<p>Formula: <math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math></p>'
        )
        result = handler.extract(element)

        assert result.tagged_text == "Formula: {{1/}}"
        assert result.inner_tags[0].raw_xml is not None
        assert "<mi>x</mi>" in result.inner_tags[0].raw_xml

    def test_svg_tag_preserved_as_raw_xml(self, handler: InnerTagHandler):
        """SVG tag structure is preserved as raw XML."""
        element = etree.fromstring(
            '<p>Icon: <svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg></p>'
        )
        result = handler.extract(element)

        assert result.tagged_text == "Icon: {{1/}}"
        assert result.inner_tags[0].raw_xml is not None
        assert "<circle" in result.inner_tags[0].raw_xml

    def test_pre_tag_preserved_as_raw_xml(self, handler: InnerTagHandler):
        """Pre tag content is preserved as raw XML."""
        element = etree.fromstring("<div>Code block:<pre>  indented\n  code</pre></div>")
        result = handler.extract(element)

        assert "{{1/}}" in result.tagged_text
        assert result.inner_tags[0].raw_xml is not None

    def test_opaque_tag_restore_returns_raw_xml(self, handler: InnerTagHandler):
        """Restoring opaque tag returns the original raw XML."""
        raw = '<code class="lang">x = 1</code>'
        inner_tags = [
            InnerTag(index=1, tag_name="code", attributes={}, is_self_closing=False, raw_xml=raw)
        ]
        result = handler.restore("See {{1/}} example.", inner_tags)

        assert result == f"See {raw} example."

    def test_opaque_tag_round_trip(self, handler: InnerTagHandler):
        """Round-trip preserves opaque tag exactly."""
        original = '<p>Run <code class="python">print("hello")</code> to test.</p>'
        element = etree.fromstring(original)

        # Extract
        extracted = handler.extract(element)

        # Simulate translation
        translated = "실행 {{1/}} 테스트하세요."

        # Restore
        restored = handler.restore(translated, extracted.inner_tags)

        assert 'class="python"' in restored
        assert 'print("hello")' in restored

    def test_mixed_opaque_and_regular_tags(self, handler: InnerTagHandler):
        """Mix of opaque and regular tags."""
        element = etree.fromstring("<p>See <b>bold</b> and <code>code</code> here.</p>")
        result = handler.extract(element)

        # b is regular, code is opaque
        assert result.tagged_text == "See {{1}}bold{{/1}} and {{2/}} here."
        assert result.inner_tags[0].raw_xml is None  # b is regular
        assert result.inner_tags[1].raw_xml is not None  # code is opaque

    def test_nested_content_in_opaque_tag_preserved(self, handler: InnerTagHandler):
        """Nested content inside opaque tag is preserved."""
        element = etree.fromstring(
            "<p>Example: <code><span class='keyword'>function</span> foo()</code></p>"
        )
        result = handler.extract(element)

        # The entire code tag including nested span should be in raw_xml
        assert result.inner_tags[0].raw_xml is not None
        assert "<span" in result.inner_tags[0].raw_xml
        assert "keyword" in result.inner_tags[0].raw_xml


class TestLogging:
    """Tests for logging behavior."""

    def test_unknown_placeholder_logs_warning(self, handler: InnerTagHandler, caplog):
        """Unknown placeholder logs a warning."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]

        with caplog.at_level(logging.WARNING):
            handler.restore("Hello {{1}}world{{/1}} {{99}}oops{{/99}}!", inner_tags)

        assert "Unknown placeholder index 99" in caplog.text
        assert "{{99}}" in caplog.text

    def test_unmatched_placeholder_filtered_before_restore(self, handler: InnerTagHandler):
        """Unmatched placeholders are filtered out before XML restoration."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]

        # Missing closing tag {{/1}} - _filter_invalid_placeholders removes {{1}}
        element = handler.restore_to_element("p", "Hello {{1}}world!", inner_tags)

        assert element is not None
        assert element.tag == "p"
        assert element.text == "Hello world!"

    def test_multiple_unknown_placeholders_log_each(self, handler: InnerTagHandler, caplog):
        """Each unknown placeholder is logged separately."""
        inner_tags = [InnerTag(index=1, tag_name="b", attributes={}, is_self_closing=False)]

        with caplog.at_level(logging.WARNING):
            handler.restore("{{1}}ok{{/1}} {{5}}a{{/5}} {{10}}b{{/10}}", inner_tags)

        # Should log warnings for both unknown indices
        assert "Unknown placeholder index 5" in caplog.text
        assert "Unknown placeholder index 10" in caplog.text
