import { describe, it, expect, afterEach } from 'vitest'
import {
  type StyleOption,
  filterAllowedStyle,
  styleTextToObject,
  normalizeInlineTag,
  computeTagStack,
  mergeTagStackPreviewStyle,
  buildNestedWrapper,
  hasSameStyle,
  mergeAdjacentSameStyle,
  flattenMatchingElements,
  findImmediateStyledAncestor,
  splitElementAtRange,
  extractStyleOptions,
  findParagraphElement,
  applyInlineStyle,
} from '../utils/inlineStyleUtils'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function para(html: string): HTMLElement {
  const p = document.createElement('p')
  p.dataset.paragraphId = 'p1'
  p.innerHTML = html
  document.body.appendChild(p)
  return p
}

function rangeCollapsedAfter(node: Node, offset: number): Range {
  const r = document.createRange()
  r.setStart(node, offset)
  r.collapse(true)
  return r
}

// ---------------------------------------------------------------------------
// filterAllowedStyle
// ---------------------------------------------------------------------------

describe('filterAllowedStyle', () => {
  it('keeps whitelisted properties', () => {
    const result = filterAllowedStyle('color: red; font-weight: bold')
    expect(result).toBe('color: red; font-weight: bold')
  })

  it('strips non-whitelisted properties', () => {
    const result = filterAllowedStyle('color: red; margin: 10px; font-size: 14px')
    expect(result).toBe('color: red')
  })

  it('deduplicates identical declarations', () => {
    const result = filterAllowedStyle('color: red; color: red')
    expect(result).toBe('color: red')
  })

  it('returns empty string for empty input', () => {
    expect(filterAllowedStyle('')).toBe('')
  })

  it('normalizes property names to lowercase', () => {
    const result = filterAllowedStyle('COLOR: red')
    expect(result).toBe('color: red')
  })
})

// ---------------------------------------------------------------------------
// styleTextToObject
// ---------------------------------------------------------------------------

describe('styleTextToObject', () => {
  it('converts kebab-case to camelCase', () => {
    const obj = styleTextToObject('font-weight: bold; background-color: blue')
    expect(obj).toMatchObject({ fontWeight: 'bold', backgroundColor: 'blue' })
  })

  it('handles empty string', () => {
    expect(styleTextToObject('')).toEqual({})
  })
})

// ---------------------------------------------------------------------------
// normalizeInlineTag
// ---------------------------------------------------------------------------

describe('normalizeInlineTag', () => {
  it('maps b → strong', () => expect(normalizeInlineTag('b')).toBe('strong'))
  it('maps i → em', () => expect(normalizeInlineTag('i')).toBe('em'))
  it('passes through strong, em, u, span, a', () => {
    for (const tag of ['strong', 'em', 'u', 'span', 'a']) {
      expect(normalizeInlineTag(tag)).toBe(tag)
    }
  })
})

// ---------------------------------------------------------------------------
// findParagraphElement
// ---------------------------------------------------------------------------

describe('findParagraphElement', () => {
  it('returns element that has data-paragraph-id', () => {
    const p = para('hello')
    expect(findParagraphElement(p)).toBe(p)
  })

  it('traverses up from text node', () => {
    const p = para('<strong>text</strong>')
    const text = p.querySelector('strong')!.firstChild as Text
    expect(findParagraphElement(text)).toBe(p)
  })

  it('returns null for null input', () => {
    expect(findParagraphElement(null)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// computeTagStack
// ---------------------------------------------------------------------------

describe('computeTagStack', () => {
  it('returns empty array for text directly in paragraph', () => {
    const p = para('plain text')
    const text = p.firstChild as Text
    expect(computeTagStack(text, p)).toEqual([])
  })

  it('returns single-level stack for <strong>text</strong>', () => {
    const p = para('<strong>bold</strong>')
    const text = p.querySelector('strong')!.firstChild as Text
    const stack = computeTagStack(text, p)
    expect(stack).toHaveLength(1)
    expect(stack[0].tag).toBe('strong')
    expect(stack[0].style).toBe('')
  })

  it('returns multi-level stack outermost-first for <b><i>text</i></b>', () => {
    const p = para('<b><i>nested</i></b>')
    const text = p.querySelector('i')!.firstChild as Text
    const stack = computeTagStack(text, p)
    expect(stack).toHaveLength(2)
    expect(stack[0].tag).toBe('b')
    expect(stack[1].tag).toBe('i')
  })

  it('captures href on <a> elements', () => {
    const p = para('<a href="http://example.com">link</a>')
    const text = p.querySelector('a')!.firstChild as Text
    const stack = computeTagStack(text, p)
    expect(stack[0].href).toBe('http://example.com')
  })

  it('filters style through whitelist', () => {
    const p = para('<span style="color: red; margin: 10px">text</span>')
    const text = p.querySelector('span')!.firstChild as Text
    const stack = computeTagStack(text, p)
    expect(stack[0].style).toBe('color: red')
  })
})

// ---------------------------------------------------------------------------
// mergeTagStackPreviewStyle
// ---------------------------------------------------------------------------

describe('mergeTagStackPreviewStyle', () => {
  it('sets fontWeight bold for <b>', () => {
    const style = mergeTagStackPreviewStyle([{ tag: 'b', style: '' }])
    expect(style).toMatchObject({ fontWeight: 'bold' })
  })

  it('sets fontStyle italic for <em>', () => {
    const style = mergeTagStackPreviewStyle([{ tag: 'em', style: '' }])
    expect(style).toMatchObject({ fontStyle: 'italic' })
  })

  it('sets textDecoration underline for <u>', () => {
    const style = mergeTagStackPreviewStyle([{ tag: 'u', style: '' }])
    expect(style).toMatchObject({ textDecoration: 'underline' })
  })

  it('sets link defaults for <a>', () => {
    const style = mergeTagStackPreviewStyle([{ tag: 'a', style: '' }])
    expect(style).toMatchObject({ textDecoration: 'underline', color: '#2563eb' })
  })

  it('merges CSS from all levels, inner overrides outer', () => {
    const style = mergeTagStackPreviewStyle([
      { tag: 'span', style: 'color: red' },
      { tag: 'span', style: 'color: blue' },
    ])
    expect(style).toMatchObject({ color: 'blue' })
  })

  it('link color not overridden by existing color', () => {
    const style = mergeTagStackPreviewStyle([{ tag: 'a', style: 'color: green' }])
    expect((style as Record<string, string>).color).toBe('green')
  })
})

// ---------------------------------------------------------------------------
// buildNestedWrapper
// ---------------------------------------------------------------------------

describe('buildNestedWrapper', () => {
  it('creates single element for single-item stack', () => {
    const { outermost, innermost } = buildNestedWrapper(document, [
      { tag: 'strong', style: '' },
    ])
    expect(outermost.tagName.toLowerCase()).toBe('strong')
    expect(outermost).toBe(innermost)
  })

  it('creates nested structure outermost → innermost', () => {
    const { outermost, innermost } = buildNestedWrapper(document, [
      { tag: 'b', style: '' },
      { tag: 'i', style: '' },
    ])
    expect(outermost.tagName.toLowerCase()).toBe('b')
    expect(innermost.tagName.toLowerCase()).toBe('i')
    expect(outermost.firstElementChild).toBe(innermost)
  })

  it('sets style attribute', () => {
    const { outermost } = buildNestedWrapper(document, [
      { tag: 'span', style: 'color: red' },
    ])
    expect(outermost.getAttribute('style')).toBe('color: red')
  })

  it('sets href on <a>', () => {
    const { outermost } = buildNestedWrapper(document, [
      { tag: 'a', style: '', href: 'http://example.com' },
    ])
    expect(outermost.getAttribute('href')).toBe('http://example.com')
  })
})

// ---------------------------------------------------------------------------
// hasSameStyle
// ---------------------------------------------------------------------------

describe('hasSameStyle', () => {
  it('returns true for identical tag/style/href', () => {
    const a = document.createElement('strong')
    const b = document.createElement('strong')
    expect(hasSameStyle(a, b)).toBe(true)
  })

  it('returns false for different tags', () => {
    const a = document.createElement('strong')
    const b = document.createElement('em')
    expect(hasSameStyle(a, b)).toBe(false)
  })

  it('returns false for different style attributes', () => {
    const a = document.createElement('span')
    a.setAttribute('style', 'color: red')
    const b = document.createElement('span')
    b.setAttribute('style', 'color: blue')
    expect(hasSameStyle(a, b)).toBe(false)
  })

  it('returns false for different href', () => {
    const a = document.createElement('a')
    a.setAttribute('href', 'http://a.com')
    const b = document.createElement('a')
    b.setAttribute('href', 'http://b.com')
    expect(hasSameStyle(a, b)).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// mergeAdjacentSameStyle
// ---------------------------------------------------------------------------

describe('mergeAdjacentSameStyle', () => {
  it('merges two adjacent <strong> elements', () => {
    const p = para('<strong>안</strong><strong>녕</strong>')
    mergeAdjacentSameStyle(p)
    expect(p.querySelectorAll('strong')).toHaveLength(1)
    expect(p.querySelector('strong')!.textContent).toBe('안녕')
  })

  it('does not merge <strong> and <em>', () => {
    const p = para('<strong>안</strong><em>녕</em>')
    mergeAdjacentSameStyle(p)
    expect(p.querySelectorAll('strong')).toHaveLength(1)
    expect(p.querySelectorAll('em')).toHaveLength(1)
  })

  it('merges nested: <b><i>안</i></b><b><i>녕</i></b> → <b><i>안녕</i></b>', () => {
    const p = para('<b><i>안</i></b><b><i>녕</i></b>')
    mergeAdjacentSameStyle(p)
    expect(p.querySelectorAll('b')).toHaveLength(1)
    expect(p.querySelectorAll('i')).toHaveLength(1)
    expect(p.querySelector('i')!.textContent).toBe('안녕')
  })

  it('merges three adjacent same-style elements', () => {
    const p = para('<em>a</em><em>b</em><em>c</em>')
    mergeAdjacentSameStyle(p)
    expect(p.querySelectorAll('em')).toHaveLength(1)
    expect(p.querySelector('em')!.textContent).toBe('abc')
  })
})

// ---------------------------------------------------------------------------
// flattenMatchingElements
// ---------------------------------------------------------------------------

describe('flattenMatchingElements', () => {
  it('unwraps same-style element in fragment', () => {
    const fragment = document.createDocumentFragment()
    const strong = document.createElement('strong')
    strong.textContent = '홍길'
    fragment.appendChild(strong)

    flattenMatchingElements(fragment, {
      key: 'k',
      tag: 'strong',
      styleText: '',
      previewStyle: {},
    })

    expect(fragment.querySelector('strong')).toBeNull()
    expect(fragment.textContent).toBe('홍길')
  })

  it('does not unwrap different-style element', () => {
    const fragment = document.createDocumentFragment()
    const strong = document.createElement('strong')
    strong.setAttribute('style', 'color: red')
    strong.textContent = 'text'
    fragment.appendChild(strong)

    flattenMatchingElements(fragment, {
      key: 'k',
      tag: 'strong',
      styleText: '',
      previewStyle: {},
    })

    expect(fragment.querySelector('strong')).not.toBeNull()
  })
})

// ---------------------------------------------------------------------------
// findImmediateStyledAncestor
// ---------------------------------------------------------------------------

describe('findImmediateStyledAncestor', () => {
  it('returns null when range is at paragraph level', () => {
    const p = para('<strong>text</strong>')
    const range = rangeCollapsedAfter(p, 0)
    expect(findImmediateStyledAncestor(range, p)).toBeNull()
  })

  it('returns the styled parent when range is inside text node in styled element', () => {
    const p = para('<strong>text</strong>')
    const strong = p.querySelector('strong')!
    const text = strong.firstChild as Text
    const range = rangeCollapsedAfter(text, 2)
    expect(findImmediateStyledAncestor(range, p)).toBe(strong)
  })

  it('returns null for text node directly in paragraph', () => {
    const p = para('plain')
    const text = p.firstChild as Text
    const range = rangeCollapsedAfter(text, 2)
    expect(findImmediateStyledAncestor(range, p)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// splitElementAtRange
// ---------------------------------------------------------------------------

describe('splitElementAtRange', () => {
  it('splits element at mid-text offset', () => {
    // <p><strong>안녕하세요</strong></p>
    // After extracting "녕" the range is inside the text node at offset 1
    // We simulate: range collapsed at offset 1 inside "안하세요" (after extract)
    const p = para('<strong>안하세요</strong>')
    const strong = p.querySelector('strong')!
    const text = strong.firstChild as Text
    const range = rangeCollapsedAfter(text, 1)  // after "안"

    splitElementAtRange(strong as HTMLElement, range)

    const strongs = p.querySelectorAll('strong')
    expect(strongs).toHaveLength(2)
    expect(strongs[0].textContent).toBe('안')
    expect(strongs[1].textContent).toBe('하세요')
  })

  it('returns a range positioned between the two halves', () => {
    const p = para('<strong>AB</strong>')
    const strong = p.querySelector('strong')!
    const text = strong.firstChild as Text
    const range = rangeCollapsedAfter(text, 1)  // after "A"

    const newRange = splitElementAtRange(strong as HTMLElement, range)

    // The new range should be between the two <strong> elements
    const strongs = p.querySelectorAll('strong')
    expect(newRange.startContainer).toBe(p)
    expect(newRange.endContainer).toBe(p)
    expect(p.childNodes[newRange.startOffset - 1]).toBe(strongs[0])
    expect(p.childNodes[newRange.endOffset]).toBe(strongs[1])
  })

  it('moves all children when split at offset 0', () => {
    const p = para('<strong>full</strong>')
    const strong = p.querySelector('strong')!
    const text = strong.firstChild as Text
    const range = rangeCollapsedAfter(text, 0)

    splitElementAtRange(strong as HTMLElement, range)

    const strongs = p.querySelectorAll('strong')
    expect(strongs).toHaveLength(2)
    expect(strongs[0].textContent).toBe('')
    expect(strongs[1].textContent).toBe('full')
  })
})

// ---------------------------------------------------------------------------
// extractStyleOptions
// ---------------------------------------------------------------------------

describe('extractStyleOptions', () => {
  it('returns empty array for plain text paragraph', () => {
    const p = para('plain text')
    expect(extractStyleOptions(p)).toEqual([])
  })

  it('extracts single <strong>', () => {
    const p = para('<strong>bold</strong>')
    const options = extractStyleOptions(p)
    expect(options).toHaveLength(1)
    expect(options[0].tag).toBe('strong')
  })

  it('normalizes <b> to strong, <i> to em', () => {
    const p = para('<b>B</b> <i>I</i>')
    const options = extractStyleOptions(p)
    const tags = options.map(o => o.tag)
    expect(tags).toContain('strong')
    expect(tags).toContain('em')
  })

  it('deduplicates same signature', () => {
    const p = para('<strong>A</strong><strong>B</strong>')
    const options = extractStyleOptions(p)
    expect(options).toHaveLength(1)
  })

  it('extracts link with label from text content (slice 0..5)', () => {
    const p = para('<a href="http://example.com">클릭하세요길어진텍스트</a>')
    const options = extractStyleOptions(p)
    expect(options).toHaveLength(1)
    expect(options[0].href).toBe('http://example.com')
    expect(options[0].label).toBe('클릭하세요')
  })

  it('skips plain text nodes (no tagStack)', () => {
    const p = para('plain <strong>bold</strong> text')
    const options = extractStyleOptions(p)
    expect(options).toHaveLength(1)
  })

  it('skips bare <a> without href (named anchor — no visual effect)', () => {
    const p = para('<a id="anchor">역에</a>')
    const options = extractStyleOptions(p)
    // href 없는 <a>는 팔레트에 나타나면 안 됨:
    // 클릭해도 href 없는 <a>로 감싸져 시각적 변화가 없음
    expect(options).toHaveLength(0)
  })

  it('includes <a> with fragment href (#section)', () => {
    const p = para('<a href="#section1">섹션 링크</a>')
    const options = extractStyleOptions(p)
    expect(options).toHaveLength(1)
    expect(options[0].href).toBe('#section1')
  })

  it('sets tagStack for multi-level nesting', () => {
    const p = para('<b><i>nested</i></b>')
    const options = extractStyleOptions(p)
    expect(options[0].tagStack).toBeDefined()
    expect(options[0].tagStack!).toHaveLength(2)
    expect(options[0].tagStack![0].tag).toBe('b')
    expect(options[0].tagStack![1].tag).toBe('i')
  })

  it('does not set tagStack for single-level', () => {
    const p = para('<strong>text</strong>')
    const options = extractStyleOptions(p)
    expect(options[0].tagStack).toBeUndefined()
  })

  it('caps at 10 options', () => {
    const html = Array.from({ length: 15 }, (_, i) =>
      `<span style="color: hsl(${i * 20}, 50%, 50%)">${i}</span>`
    ).join('')
    const p = para(html)
    const options = extractStyleOptions(p)
    expect(options.length).toBeLessThanOrEqual(10)
  })
})

// ---------------------------------------------------------------------------
// applyInlineStyle (버그 재현 테스트: 링크 포함 전체 텍스트 선택 후 링크 적용)
// ---------------------------------------------------------------------------

describe('applyInlineStyle — link over cross-node selection', () => {
  function makeOption(href: string): StyleOption {
    return { key: 'k', tag: 'a', styleText: '', previewStyle: { color: '#2563eb', textDecoration: 'underline' }, href }
  }

  function setSelection(range: Range): void {
    const sel = window.getSelection()!
    sel.removeAllRanges()
    sel.addRange(range)
  }

  afterEach(() => {
    document.body.innerHTML = ''
    window.getSelection()?.removeAllRanges()
  })

  // 케이스 1: <p>지<a>역에</a> 있다면, </p> → 전체 선택(paragraph level) → 링크 전체 적용
  it('[p offset] 전체 선택 후 링크 적용: 모든 텍스트가 링크로 감싸짐', () => {
    const p = document.createElement('p')
    p.dataset.paragraphId = 'p1'
    p.innerHTML = '지<a href="ch1">역에</a> 있다면, '
    document.body.appendChild(p)

    const range = document.createRange()
    range.setStart(p, 0)     // <p> 자식 인덱스 0 앞
    range.setEnd(p, 3)       // <p> 자식 인덱스 3 뒤 (3개 자식 모두 포함)
    setSelection(range)

    const changed = applyInlineStyle(document, makeOption('ch1'))
    expect(changed).toBe(true)
    // 전체 텍스트가 <a> 안에 있어야 함
    expect(p.querySelector('a')?.textContent).toBe('지역에 있다면, ')
    // 링크 밖에 텍스트가 없어야 함
    expect(p.childNodes.length).toBe(1)  // 빈 텍스트 노드 제외하면 a 하나
  })

  // 케이스 2: startContainer = text "지" (텍스트 노드 기준 선택)
  it('[text node] 텍스트 노드 기준 전체 선택 후 링크 적용', () => {
    const p = document.createElement('p')
    p.dataset.paragraphId = 'p1'
    p.innerHTML = '지<a href="ch1">역에</a> 있다면, '
    document.body.appendChild(p)

    const firstText = p.firstChild as Text          // "지"
    const lastText = p.lastChild as Text            // " 있다면, "

    const range = document.createRange()
    range.setStart(firstText, 0)
    range.setEnd(lastText, lastText.length)
    setSelection(range)

    const changed = applyInlineStyle(document, makeOption('ch1'))
    expect(changed).toBe(true)
    expect(p.querySelector('a')?.textContent).toBe('지역에 있다면, ')
  })

  // 케이스 3: 링크 텍스트만 선택 → 동일 링크 적용 → no-op (same style)
  it('[no-op] 이미 링크인 텍스트만 선택 후 동일 링크 적용 → 내용 유지', () => {
    const p = document.createElement('p')
    p.dataset.paragraphId = 'p1'
    p.innerHTML = '지<a href="ch1">역에</a> 있다면, '
    document.body.appendChild(p)

    const aEl = p.querySelector('a')!
    const innerText = aEl.firstChild as Text        // "역에"

    const range = document.createRange()
    range.setStart(innerText, 0)
    range.setEnd(innerText, innerText.length)
    setSelection(range)

    applyInlineStyle(document, makeOption('ch1'))
    // 텍스트 내용은 유지되어야 함 (no-op이거나 제자리 삽입)
    expect(p.textContent).toBe('지역에 있다면, ')
    // 링크는 여전히 있어야 함
    expect(p.querySelector('a[href="ch1"]')).not.toBeNull()
  })

  // 케이스 4: 링크 내부에서 시작해서 외부까지 선택 (startContainer = text "역에" at 0)
  it('[partial] 링크 내부에서 시작, 링크 외부까지 선택 → 선택 범위가 링크로 감싸짐', () => {
    const p = document.createElement('p')
    p.dataset.paragraphId = 'p1'
    p.innerHTML = '지<a href="ch1">역에</a> 있다면, '
    document.body.appendChild(p)

    const aEl = p.querySelector('a')!
    const innerText = aEl.firstChild as Text        // "역에"
    const lastText = p.lastChild as Text            // " 있다면, "

    const range = document.createRange()
    range.setStart(innerText, 0)
    range.setEnd(lastText, lastText.length)
    setSelection(range)

    const changed = applyInlineStyle(document, makeOption('ch1'))
    expect(changed).toBe(true)
    // 선택된 텍스트 "역에 있다면, "이 링크 안에 있어야 함
    expect(p.textContent).toBe('지역에 있다면, ')
    // "지"는 링크 밖
    const aText = p.querySelector('a')?.textContent
    expect(aText).toContain('역에')
    expect(aText).toContain('있다면')
  })
})
