"""Tests for TranslatableElementFilter."""

import pytest
from lxml import etree

from src.matchers.implementations import TextEmergenceMatcher, AllElementsMatcher
from src.pipeline.filters import TranslatableElementFilter


@pytest.fixture
def text_emergence_filter() -> TranslatableElementFilter:
    """Filter wrapping TextEmergenceMatcher."""
    return TranslatableElementFilter(TextEmergenceMatcher())


@pytest.fixture
def all_elements_filter() -> TranslatableElementFilter:
    """Filter wrapping AllElementsMatcher."""
    return TranslatableElementFilter(AllElementsMatcher())


class TestTranslatableElementFilter:
    """Tests for TranslatableElementFilter."""

    def test_matches_regular_paragraph(self, text_emergence_filter: TranslatableElementFilter):
        """Regular paragraph matches."""
        html = "<html><body><p>Hello world</p></body></html>"
        root = etree.fromstring(html)
        p = root.find(".//p")

        text_emergence_filter.reset()
        assert text_emergence_filter(p) is True

    def test_excludes_code_element(self, all_elements_filter: TranslatableElementFilter):
        """Code element itself is excluded."""
        html = "<html><body><code>x = 1</code></body></html>"
        root = etree.fromstring(html)
        code = root.find(".//code")

        assert all_elements_filter(code) is False

    def test_excludes_element_inside_code(self, all_elements_filter: TranslatableElementFilter):
        """Element inside code is excluded."""
        html = "<html><body><code><span>keyword</span></code></body></html>"
        root = etree.fromstring(html)
        span = root.find(".//span")

        assert all_elements_filter(span) is False

    def test_excludes_element_inside_pre(self, all_elements_filter: TranslatableElementFilter):
        """Element inside pre is excluded."""
        html = "<html><body><pre><code>code here</code></pre></body></html>"
        root = etree.fromstring(html)
        code = root.find(".//code")

        assert all_elements_filter(code) is False

    def test_excludes_element_inside_script(self, all_elements_filter: TranslatableElementFilter):
        """Element inside script is excluded."""
        html = "<html><body><script>var x = 1;</script></body></html>"
        root = etree.fromstring(html)
        script = root.find(".//script")

        assert all_elements_filter(script) is False

    def test_excludes_element_inside_style(self, all_elements_filter: TranslatableElementFilter):
        """Element inside style is excluded."""
        html = "<html><body><style>.cls { color: red; }</style></body></html>"
        root = etree.fromstring(html)
        style = root.find(".//style")

        assert all_elements_filter(style) is False

    def test_excludes_element_inside_math(self, all_elements_filter: TranslatableElementFilter):
        """Element inside math is excluded."""
        html = '<html><body><math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math></body></html>'
        root = etree.fromstring(html)
        mi = root.find(".//{http://www.w3.org/1998/Math/MathML}mi")

        if mi is not None:
            assert all_elements_filter(mi) is False

    def test_excludes_element_inside_svg(self, all_elements_filter: TranslatableElementFilter):
        """Element inside svg is excluded."""
        html = '<html><body><svg xmlns="http://www.w3.org/2000/svg"><text>label</text></svg></body></html>'
        root = etree.fromstring(html)
        text = root.find(".//{http://www.w3.org/2000/svg}text")

        if text is not None:
            assert all_elements_filter(text) is False

    def test_excludes_element_inside_head(self, all_elements_filter: TranslatableElementFilter):
        """Element inside head is excluded."""
        html = "<html><head><title>Page Title</title></head><body></body></html>"
        root = etree.fromstring(html)
        title = root.find(".//title")

        assert all_elements_filter(title) is False

    def test_excludes_kbd_element(self, all_elements_filter: TranslatableElementFilter):
        """kbd element is excluded."""
        html = "<html><body><p>Press <kbd>Enter</kbd></p></body></html>"
        root = etree.fromstring(html)
        kbd = root.find(".//kbd")

        assert all_elements_filter(kbd) is False

    def test_excludes_samp_element(self, all_elements_filter: TranslatableElementFilter):
        """samp element is excluded."""
        html = "<html><body><p>Output: <samp>Hello</samp></p></body></html>"
        root = etree.fromstring(html)
        samp = root.find(".//samp")

        assert all_elements_filter(samp) is False

    def test_excludes_var_element(self, all_elements_filter: TranslatableElementFilter):
        """var element is excluded."""
        html = "<html><body><p>Variable <var>x</var></p></body></html>"
        root = etree.fromstring(html)
        var = root.find(".//var")

        assert all_elements_filter(var) is False

    def test_includes_regular_inline_tags(self, text_emergence_filter: TranslatableElementFilter):
        """Regular inline tags like b, em are included."""
        html = "<html><body><p>Hello <b>world</b></p></body></html>"
        root = etree.fromstring(html)
        p = root.find(".//p")

        text_emergence_filter.reset()
        assert text_emergence_filter(p) is True

    def test_deeply_nested_inside_untranslatable(
        self, all_elements_filter: TranslatableElementFilter
    ):
        """Deeply nested element inside untranslatable is excluded."""
        html = """
        <html><body>
            <pre>
                <code>
                    <span class="keyword">
                        <b>function</b>
                    </span>
                </code>
            </pre>
        </body></html>
        """
        root = etree.fromstring(html)
        b = root.find(".//b")

        assert all_elements_filter(b) is False

    def test_reset_delegates_to_inner_matcher(
        self, text_emergence_filter: TranslatableElementFilter
    ):
        """reset() delegates to inner matcher."""
        # Just verify it doesn't raise an error
        text_emergence_filter.reset()

    def test_sibling_after_code_is_included(
        self, text_emergence_filter: TranslatableElementFilter
    ):
        """Sibling paragraph after code block is included."""
        html = "<html><body><code>x = 1</code><p>Description here</p></body></html>"
        root = etree.fromstring(html)
        p = root.find(".//p")

        text_emergence_filter.reset()
        assert text_emergence_filter(p) is True


class TestFilterWithRealDocument:
    """Integration tests with realistic document structures."""

    def test_technical_documentation(self, text_emergence_filter: TranslatableElementFilter):
        """Technical documentation with code examples."""
        html = """
        <html><body>
            <h1>Tutorial</h1>
            <p>First, install the package:</p>
            <pre><code>pip install mypackage</code></pre>
            <p>Then use it like this:</p>
            <pre><code>
                import mypackage
                mypackage.run()
            </code></pre>
            <p>That's all!</p>
        </body></html>
        """
        root = etree.fromstring(html)
        text_emergence_filter.reset()

        # Paragraphs should match
        paragraphs = root.findall(".//p")
        for p in paragraphs:
            assert text_emergence_filter(p) is True

        # Code inside pre should not match
        codes = root.findall(".//code")
        for code in codes:
            assert text_emergence_filter(code) is False

    def test_math_formula_in_paragraph(self, text_emergence_filter: TranslatableElementFilter):
        """Paragraph containing math formula."""
        html = """
        <html><body>
            <p>The formula <math xmlns="http://www.w3.org/1998/Math/MathML">
                <mi>E</mi><mo>=</mo><mi>m</mi><msup><mi>c</mi><mn>2</mn></msup>
            </math> is famous.</p>
        </body></html>
        """
        root = etree.fromstring(html)
        text_emergence_filter.reset()

        # Paragraph should match
        p = root.find(".//p")
        assert text_emergence_filter(p) is True

        # Math element should not match
        math = root.find(".//{http://www.w3.org/1998/Math/MathML}math")
        if math is not None:
            assert text_emergence_filter(math) is False
