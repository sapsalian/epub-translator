import type { CSSProperties } from 'react'

export interface StyleTagNode {
  tag: string
  style: string
  href?: string
}

export interface StyleOption {
  key: string
  tag: string
  styleText: string
  previewStyle: CSSProperties
  label?: string
  href?: string
  tagStack?: StyleTagNode[]
}

export const STYLE_WHITELIST = new Set([
  'color',
  'background-color',
  'font-weight',
  'font-style',
  'text-decoration',
  'font-family',
  'letter-spacing',
])

export const ALLOWED_PREVIEW_PROPS = new Set([
  'fontFamily',
  'color',
  'backgroundColor',
  'fontWeight',
  'fontStyle',
  'textDecoration',
  'letterSpacing',
])

export function filterAllowedStyle(styleText: string): string {
  const declarations = styleText
    .split(';')
    .map(declaration => declaration.trim())
    .filter(Boolean)
    .map(declaration => {
      const splitIndex = declaration.indexOf(':')
      if (splitIndex <= 0) return null
      const property = declaration.slice(0, splitIndex).trim().toLowerCase()
      const value = declaration.slice(splitIndex + 1).trim()
      if (!STYLE_WHITELIST.has(property) || value.length === 0) return null
      return `${property}: ${value}`
    })
    .filter((declaration): declaration is string => declaration !== null)

  return Array.from(new Set(declarations)).join('; ')
}

export function styleTextToObject(styleText: string): CSSProperties {
  const styleObject: Record<string, string> = {}
  styleText.split(';').forEach(declaration => {
    const splitIndex = declaration.indexOf(':')
    if (splitIndex <= 0) return
    const property = declaration.slice(0, splitIndex).trim()
    const value = declaration.slice(splitIndex + 1).trim()
    if (!property || !value) return
    const camelKey = property.replace(/-([a-z])/g, (_, char: string) => char.toUpperCase())
    styleObject[camelKey] = value
  })
  return styleObject as CSSProperties
}

export function filterPreviewStyle(styleObject: Record<string, string>): CSSProperties {
  const filtered: Record<string, string> = {}
  for (const [key, value] of Object.entries(styleObject)) {
    if (ALLOWED_PREVIEW_PROPS.has(key)) {
      filtered[key] = value
    }
  }
  return filtered as CSSProperties
}

export function normalizeInlineTag(tagName: string): string {
  if (tagName === 'b') return 'strong'
  if (tagName === 'i') return 'em'
  return tagName
}

export function findParagraphElement(node: Node | null): HTMLElement | null {
  if (!node) return null
  if (node instanceof HTMLElement && node.dataset.paragraphId) return node
  const element = node instanceof HTMLElement ? node : node.parentElement
  return element?.closest<HTMLElement>('[data-paragraph-id]') ?? null
}

export function computeTagStack(textNode: Text, stopAt: Element): StyleTagNode[] {
  const stack: StyleTagNode[] = []
  let current: Element | null = textNode.parentElement
  while (current && current !== stopAt) {
    const tag = current.tagName.toLowerCase()
    const style = filterAllowedStyle(current.getAttribute('style') ?? '')
    const href = tag === 'a' ? (current.getAttribute('href') ?? undefined) : undefined
    stack.unshift({ tag, style, href })
    current = current.parentElement
  }
  return stack
}

export function mergeTagStackPreviewStyle(tagStack: StyleTagNode[]): CSSProperties {
  const merged: Record<string, string> = {}
  for (const node of tagStack) {
    Object.assign(merged, styleTextToObject(node.style) as Record<string, string>)
    if (node.tag === 'strong' || node.tag === 'b') merged.fontWeight = 'bold'
    if (node.tag === 'em' || node.tag === 'i') merged.fontStyle = 'italic'
    if (node.tag === 'u') merged.textDecoration = 'underline'
    if (node.tag === 'a') {
      if (!merged.textDecoration) merged.textDecoration = 'underline'
      if (!merged.color) merged.color = '#2563eb'
    }
  }
  return filterPreviewStyle(merged as Record<string, string>)
}

export function buildNestedWrapper(
  doc: Document,
  tagStack: StyleTagNode[],
): { outermost: Element; innermost: Element } {
  const outermost = doc.createElement(tagStack[0].tag)
  if (tagStack[0].style) outermost.setAttribute('style', tagStack[0].style)
  if (tagStack[0].href) outermost.setAttribute('href', tagStack[0].href)

  let innermost: Element = outermost
  for (let i = 1; i < tagStack.length; i++) {
    const child = doc.createElement(tagStack[i].tag)
    if (tagStack[i].style) child.setAttribute('style', tagStack[i].style)
    if (tagStack[i].href) child.setAttribute('href', tagStack[i].href!)
    innermost.appendChild(child)
    innermost = child
  }
  return { outermost, innermost }
}

export function hasSameStyle(a: Element, b: Element): boolean {
  return (
    a.tagName === b.tagName &&
    (a.getAttribute('style') ?? '') === (b.getAttribute('style') ?? '') &&
    (a.getAttribute('href') ?? '') === (b.getAttribute('href') ?? '')
  )
}

export function mergeSiblings(parent: Element): void {
  const children = [...parent.childNodes]
  let i = 0
  while (i < children.length - 1) {
    const a = children[i]
    const b = children[i + 1]
    if (a instanceof Element && b instanceof Element && hasSameStyle(a, b)) {
      while (b.firstChild) a.appendChild(b.firstChild)
      b.remove()
      children.splice(i + 1, 1)
      mergeSiblings(a)
    } else {
      i++
    }
  }
}

export function mergeAdjacentSameStyle(paragraph: Element): void {
  mergeSiblings(paragraph)
  for (const child of [...paragraph.children]) {
    mergeAdjacentSameStyle(child)
  }
}

export function flattenMatchingElements(fragment: DocumentFragment, option: StyleOption): void {
  const matching = [...fragment.querySelectorAll(option.tag)]
  for (const el of matching) {
    const sameStyle =
      filterAllowedStyle(el.getAttribute('style') ?? '') === option.styleText &&
      (el.getAttribute('href') ?? undefined) === option.href
    if (sameStyle) el.replaceWith(...el.childNodes)
  }
}

export function findImmediateStyledAncestor(
  range: Range,
  paragraph: HTMLElement,
): HTMLElement | null {
  const container = range.startContainer
  if (container === paragraph) return null
  if (container instanceof HTMLElement && container !== paragraph) return container
  if (container.nodeType === Node.TEXT_NODE) {
    const parent = (container as Text).parentElement
    if (parent && parent !== paragraph) return parent
  }
  return null
}

export function splitElementAtRange(element: HTMLElement, range: Range): Range {
  const clone = element.cloneNode(false) as HTMLElement
  const doc = element.ownerDocument

  let splitPoint: ChildNode | null = null

  if (range.startContainer === element) {
    splitPoint = element.childNodes[range.startOffset] ?? null
  } else if (
    range.startContainer.nodeType === Node.TEXT_NODE &&
    range.startContainer.parentNode === element
  ) {
    const textNode = range.startContainer as Text
    if (range.startOffset === 0) {
      splitPoint = textNode
    } else if (range.startOffset >= textNode.length) {
      splitPoint = textNode.nextSibling
    } else {
      splitPoint = textNode.splitText(range.startOffset)
    }
  }

  let current: ChildNode | null = splitPoint
  while (current) {
    const next = current.nextSibling
    clone.appendChild(current)
    current = next
  }

  element.parentNode?.insertBefore(clone, element.nextSibling)

  const newRange = doc.createRange()
  newRange.setStartAfter(element)
  newRange.setEndBefore(clone)
  return newRange
}

export function extractStyleOptions(paragraph: HTMLElement): StyleOption[] {
  const options: StyleOption[] = []
  const signatures = new Set<string>()

  const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT)
  let textNode: Text | null
  while ((textNode = walker.nextNode() as Text | null)) {
    if (!textNode.textContent?.trim()) continue

    const tagStack = computeTagStack(textNode, paragraph)
    if (tagStack.length === 0) continue

    const signature = tagStack.map(n => `${n.tag}|${n.style}|${n.href ?? ''}`).join('>')
    if (signatures.has(signature)) continue
    signatures.add(signature)

    const previewStyle = mergeTagStackPreviewStyle(tagStack)
    const outermost = tagStack[0]
    const hasLink = tagStack.some(n => n.tag === 'a')
    const label = hasLink
      ? (textNode.textContent?.trim().slice(0, 5) || outermost.href?.slice(0, 5) || '링크')
      : undefined

    options.push({
      key: `inline-${options.length}`,
      tag: normalizeInlineTag(outermost.tag),
      styleText: outermost.style,
      previewStyle,
      label,
      href: outermost.href,
      tagStack: tagStack.length > 1 ? tagStack : undefined,
    })

    if (options.length >= 10) break
  }

  return options
}

export function applyInlineStyle(doc: Document, option: StyleOption): boolean {
  const selection = doc.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return false

  const range = selection.getRangeAt(0)
  const paragraph = findParagraphElement(range.commonAncestorContainer) as HTMLElement | null
  if (!paragraph) return false

  if (option.tagStack && option.tagStack.length > 1) {
    const { outermost, innermost } = buildNestedWrapper(doc, option.tagStack)
    const fragment = range.extractContents()
    innermost.appendChild(fragment)
    range.insertNode(outermost)
    mergeAdjacentSameStyle(paragraph)
    return true
  }

  const contentFragment = range.extractContents()
  flattenMatchingElements(contentFragment, option)

  const styledContainer = findImmediateStyledAncestor(range, paragraph)

  if (styledContainer) {
    const containerTag = normalizeInlineTag(styledContainer.tagName.toLowerCase())
    const containerStyle = filterAllowedStyle(styledContainer.getAttribute('style') ?? '')
    const containerHref = styledContainer.getAttribute('href') ?? undefined
    const matches =
      containerTag === option.tag &&
      containerStyle === option.styleText &&
      containerHref === option.href

    if (matches) {
      range.insertNode(contentFragment)
    } else {
      const insertRange = splitElementAtRange(styledContainer, range)
      const wrapper = doc.createElement(option.tag)
      if (option.styleText) wrapper.setAttribute('style', option.styleText)
      if (option.href) wrapper.setAttribute('href', option.href)
      wrapper.appendChild(contentFragment)
      insertRange.insertNode(wrapper)
    }
  } else {
    const wrapper = doc.createElement(option.tag)
    if (option.styleText) wrapper.setAttribute('style', option.styleText)
    if (option.href) wrapper.setAttribute('href', option.href)
    wrapper.appendChild(contentFragment)
    range.insertNode(wrapper)
  }

  mergeAdjacentSameStyle(paragraph)
  return true
}
