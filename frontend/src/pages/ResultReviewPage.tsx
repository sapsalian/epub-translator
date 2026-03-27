import {
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Languages, Save } from 'lucide-react'
import { toast } from 'sonner'

import {
  apiClient,
  type ContentEdit,
  extractErrorMessage,
  type JobChapter,
  type JobChapterContent,
  type JobInfo,
} from '../api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface IframePanelProps {
  html: string
  hidden: boolean
  iframeRef: RefObject<HTMLIFrameElement | null>
  title: string
  onLoad?: () => void
}

interface StyleTagNode {
  tag: string
  style: string
  href?: string
}

interface StyleOption {
  key: string
  tag: string
  styleText: string
  previewStyle: CSSProperties
  label?: string
  href?: string
  tagStack?: StyleTagNode[]
}

interface PaletteState {
  top: number
  left: number
  paragraphId: string
  options: StyleOption[]
}

const STYLE_WHITELIST = new Set([
  'color',
  'background-color',
  'font-weight',
  'font-style',
  'text-decoration',
  'font-family',
  'letter-spacing',
])

const ALLOWED_PREVIEW_PROPS = new Set([
  'fontFamily',
  'color',
  'backgroundColor',
  'fontWeight',
  'fontStyle',
  'textDecoration',
  'letterSpacing',
])

function IframePanel({ html, hidden, iframeRef, title, onLoad }: IframePanelProps) {
  return (
    <iframe
      ref={iframeRef}
      srcDoc={html}
      sandbox="allow-same-origin allow-scripts"
      onLoad={onLoad}
      style={{
        width: '100%',
        height: '100%',
        border: 'none',
        display: hidden ? 'none' : 'block',
        background: 'white',
      }}
      title={title}
    />
  )
}

function normalizeEditableHtml(html: string): string {
  return html
    .replace(/<div><br><\/div>/gi, '<br/>')
    .replace(/<\/div>\s*<div>/gi, '<br/>')
    .replace(/<div>/gi, '')
    .replace(/<\/div>/gi, '')
    .replace(/<br\s*\/?>/gi, '<br/>')
    .trim()
}

function findParagraphElement(node: Node | null): HTMLElement | null {
  if (!node) return null
  if (node instanceof HTMLElement && node.dataset.paragraphId) return node
  const element = node instanceof HTMLElement ? node : node.parentElement
  return element?.closest<HTMLElement>('[data-paragraph-id]') ?? null
}

function insertLineBreak(doc: Document): void {
  const selection = doc.getSelection()
  if (!selection || selection.rangeCount === 0) return
  const range = selection.getRangeAt(0)
  range.deleteContents()
  const br = doc.createElement('br')
  range.insertNode(br)
  range.setStartAfter(br)
  range.collapse(true)
  selection.removeAllRanges()
  selection.addRange(range)
}

function insertPlainText(doc: Document, text: string): void {
  const selection = doc.getSelection()
  if (!selection || selection.rangeCount === 0) return
  const range = selection.getRangeAt(0)
  range.deleteContents()

  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const fragment = doc.createDocumentFragment()
  lines.forEach((line, index) => {
    if (index > 0) {
      fragment.appendChild(doc.createElement('br'))
    }
    fragment.appendChild(doc.createTextNode(line))
  })

  range.insertNode(fragment)
  range.collapse(false)
  selection.removeAllRanges()
  selection.addRange(range)
}

function getTopmostParagraphId(iframe: HTMLIFrameElement | null): string | null {
  const doc = iframe?.contentWindow?.document
  if (!doc) return null

  const elements = doc.querySelectorAll<HTMLElement>('[data-paragraph-id]')
  for (const element of elements) {
    const rect = element.getBoundingClientRect()
    if (rect.bottom > 24) {
      return element.dataset.paragraphId ?? null
    }
  }
  return null
}

function scrollToParagraph(iframe: HTMLIFrameElement | null, paragraphId: string | null): void {
  if (!iframe || !paragraphId) return
  const doc = iframe.contentWindow?.document
  if (!doc) return

  doc
    .querySelector<HTMLElement>(`[data-paragraph-id="${paragraphId}"]`)
    ?.scrollIntoView({ block: 'start', behavior: 'auto' })
}

function filterAllowedStyle(styleText: string): string {
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

function styleTextToObject(styleText: string): CSSProperties {
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

function filterPreviewStyle(styleObject: Record<string, string>): CSSProperties {
  const filtered: Record<string, string> = {}
  for (const [key, value] of Object.entries(styleObject)) {
    if (ALLOWED_PREVIEW_PROPS.has(key)) {
      filtered[key] = value
    }
  }
  return filtered as CSSProperties
}

function normalizeInlineTag(tagName: string): string {
  if (tagName === 'b') return 'strong'
  if (tagName === 'i') return 'em'
  return tagName
}

function computeTagStack(textNode: Text, stopAt: Element): StyleTagNode[] {
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

function mergeTagStackPreviewStyle(tagStack: StyleTagNode[]): CSSProperties {
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

function buildNestedWrapper(
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

function extractStyleOptions(paragraph: HTMLElement): StyleOption[] {
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

function hasSelectionInsideParagraph(doc: Document, paragraphId: string): boolean {
  const selection = doc.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return false
  const paragraph = findParagraphElement(selection.getRangeAt(0).commonAncestorContainer)
  return paragraph?.dataset.paragraphId === paragraphId
}

function findSelectionParagraph(selection: Selection): HTMLElement | null {
  if (selection.rangeCount === 0) return null
  const range = selection.getRangeAt(0)
  return (
    findParagraphElement(range.commonAncestorContainer) ??
    findParagraphElement(selection.anchorNode) ??
    findParagraphElement(selection.focusNode)
  )
}

function applyInlineStyle(doc: Document, option: StyleOption): boolean {
  const selection = doc.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return false

  const range = selection.getRangeAt(0)

  if (option.tagStack && option.tagStack.length > 1) {
    const { outermost, innermost } = buildNestedWrapper(doc, option.tagStack)
    const fragment = range.extractContents()
    innermost.appendChild(fragment)
    range.insertNode(outermost)
    return true
  }

  const wrapper = doc.createElement(option.tag)
  if (option.styleText) wrapper.setAttribute('style', option.styleText)
  if (option.href) wrapper.setAttribute('href', option.href)

  try {
    range.surroundContents(wrapper)
  } catch {
    const fragment = range.extractContents()
    wrapper.appendChild(fragment)
    range.insertNode(wrapper)
  }

  return true
}

export function ResultReviewPage() {
  const { id: jobId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [job, setJob] = useState<JobInfo | null>(null)
  const [chapters, setChapters] = useState<JobChapter[]>([])
  const [selectedChapterId, setSelectedChapterId] = useState<string>('')
  const [chapterContent, setChapterContent] = useState<JobChapterContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [chapterLoading, setChapterLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isEditMode, setIsEditMode] = useState(true)
  const [discardKey, setDiscardKey] = useState(0)
  const [showSource, setShowSource] = useState(false)
  const [baseTranslations, setBaseTranslations] = useState<Record<string, string>>({})
  const [draftTranslations, setDraftTranslations] = useState<Record<string, string>>({})
  const [activeParagraphId, setActiveParagraphId] = useState<string | null>(null)
  const [palette, setPalette] = useState<PaletteState | null>(null)
  const [saving, setSaving] = useState(false)

  const translationRef = useRef<HTMLIFrameElement>(null)
  const sourceRef = useRef<HTMLIFrameElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)
  const isEditModeRef = useRef(true)
  const pendingFragmentRef = useRef<string | null>(null)
  const showSourceRef = useRef(false)
  const baseTranslationsRef = useRef<Record<string, string>>({})
  const activeParagraphIdRef = useRef<string | null>(null)
  const saveRef = useRef<() => Promise<void>>(async () => {})

  // xhtml_path basename → chapter_id (Phase 3 link navigation)
  const chapterMap = useMemo(
    () => new Map(chapters.map(c => [c.xhtml_path.split('/').pop() ?? '', c.chapter_id])),
    [chapters],
  )

  useEffect(() => {
    if (!jobId) return

    const load = async () => {
      setLoading(true)
      setError(null)

      try {
        const jobData = await apiClient.getJob(jobId)
        if (jobData.state !== 'done') {
          toast.error('완료된 작업만 결과 뷰어에서 열 수 있습니다.')
          navigate('/', { replace: true })
          return
        }

        const chapterList = await apiClient.getJobChapters(jobId)
        setJob(jobData)
        setChapters(chapterList)
        setSelectedChapterId(current => current || chapterList[0]?.chapter_id || '')
      } catch (err) {
        setError(extractErrorMessage(err))
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [jobId, navigate])

  const pendingEdits = useMemo<ContentEdit[]>(() => {
    const edits: ContentEdit[] = []
    for (const [id, translation] of Object.entries(draftTranslations)) {
      if (translation !== (baseTranslations[id] ?? '')) {
        edits.push({ id, translation })
      }
    }
    return edits
  }, [baseTranslations, draftTranslations])

  const hasUnsavedChanges = pendingEdits.length > 0

  useEffect(() => {
    if (!jobId || !selectedChapterId) return

    const loadChapter = async () => {
      setChapterLoading(true)
      setError(null)

      try {
        const data = await apiClient.getJobChapterContent(jobId, selectedChapterId)
        setChapterContent(data)
      } catch (err) {
        setError(extractErrorMessage(err))
      } finally {
        setChapterLoading(false)
      }
    }

    loadChapter()
  }, [jobId, selectedChapterId])

  useEffect(() => {
    if (!chapterContent) return
    const nextBase: Record<string, string> = {}
    chapterContent.paragraphs.forEach(paragraph => {
      nextBase[paragraph.id] = normalizeEditableHtml(paragraph.translation)
    })
    setBaseTranslations(nextBase)
    setDraftTranslations({})
    setActiveParagraphId(null)
    setPalette(null)
  }, [chapterContent?.chapter_id])

  useEffect(() => {
    isEditModeRef.current = isEditMode
  }, [isEditMode])

  useEffect(() => {
    showSourceRef.current = showSource
    if (showSource) setPalette(null)
  }, [showSource])

  useEffect(() => {
    baseTranslationsRef.current = baseTranslations
  }, [baseTranslations])

  useEffect(() => {
    activeParagraphIdRef.current = activeParagraphId
  }, [activeParagraphId])

  useEffect(() => {
    if (!hasUnsavedChanges) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  useEffect(
    () => () => {
      cleanupRef.current?.()
    },
    [],
  )

  useEffect(() => {
    const doc = translationRef.current?.contentWindow?.document
    if (!doc) return
    const paragraphs = doc.querySelectorAll<HTMLElement>('[data-paragraph-id]')
    paragraphs.forEach(paragraph => {
      const paragraphId = paragraph.dataset.paragraphId ?? ''
      const isDirty = Object.prototype.hasOwnProperty.call(draftTranslations, paragraphId)
      const isActive = paragraphId === activeParagraphId
      paragraph.style.backgroundColor = isDirty ? 'rgba(250, 204, 21, 0.2)' : ''
      paragraph.style.boxShadow = isActive ? 'inset 0 0 0 2px rgba(59, 130, 246, 0.55)' : ''
    })
  }, [activeParagraphId, chapterContent?.chapter_id, draftTranslations])

  const sourceAvailable = chapterContent?.source_html != null
  const sourceMissing = !sourceAvailable && !chapterLoading && !!chapterContent
  const chapterNumberWidth = Math.max(2, String(chapters.length || 1).length)

  useEffect(() => {
    if (!sourceAvailable && showSource) {
      setShowSource(false)
    }
  }, [showSource, sourceAvailable])

  const syncDraftFromParagraph = (paragraph: HTMLElement): void => {
    const paragraphId = paragraph.dataset.paragraphId
    if (!paragraphId) return

    const normalized = normalizeEditableHtml(paragraph.innerHTML)
    const original = baseTranslationsRef.current[paragraphId] ?? ''

    setDraftTranslations(previous => {
      if (normalized === original) {
        if (!(paragraphId in previous)) return previous
        const next = { ...previous }
        delete next[paragraphId]
        return next
      }
      if (previous[paragraphId] === normalized) return previous
      return { ...previous, [paragraphId]: normalized }
    })
  }

  const refreshPaletteFromSelection = (): void => {
    const iframe = translationRef.current
    const doc = iframe?.contentWindow?.document
    if (!iframe || !doc || showSourceRef.current) {
      setPalette(null)
      return
    }

    const selection = doc.getSelection()
    const iframeRect = iframe.getBoundingClientRect()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      const fallbackParagraphId = activeParagraphIdRef.current
      if (!fallbackParagraphId) {
        setPalette(null)
        return
      }

      const fallbackParagraph = doc.querySelector<HTMLElement>(
        `[data-paragraph-id="${fallbackParagraphId}"]`,
      )
      if (!fallbackParagraph) {
        setPalette(null)
        return
      }

      const paragraphRect = fallbackParagraph.getBoundingClientRect()
      const left = Math.min(
        window.innerWidth - 16,
        Math.max(16, iframeRect.left + paragraphRect.left + paragraphRect.width / 2),
      )
      const top = Math.max(40, iframeRect.top + paragraphRect.top + 8)

      setPalette({
        paragraphId: fallbackParagraphId,
        options: extractStyleOptions(fallbackParagraph),
        top,
        left,
      })
      return
    }

    const range = selection.getRangeAt(0)
    const paragraph = findSelectionParagraph(selection)
    const paragraphId = paragraph?.dataset.paragraphId
    if (!paragraph || !paragraphId) {
      setPalette(null)
      return
    }

    const rect = range.getBoundingClientRect()
    const targetRect =
      rect.width === 0 && rect.height === 0 ? paragraph.getBoundingClientRect() : rect
    const rawLeft = iframeRect.left + targetRect.left + targetRect.width / 2
    const left = Math.min(window.innerWidth - 16, Math.max(16, rawLeft))
    const top = Math.max(16, iframeRect.top + targetRect.top - 12)

    setPalette({
      paragraphId,
      options: extractStyleOptions(paragraph),
      top,
      left,
    })
  }

  const handleSave = async (): Promise<void> => {
    if (!jobId || pendingEdits.length === 0 || chapterLoading || saving) return

    setSaving(true)
    try {
      await apiClient.saveJobContent(jobId, pendingEdits)
      setBaseTranslations(previous => {
        const next = { ...previous }
        pendingEdits.forEach(edit => {
          next[edit.id] = edit.translation
        })
        return next
      })
      setDraftTranslations({})
      setPalette(null)
      toast.success(`${pendingEdits.length}개 문단을 저장했습니다.`)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  saveRef.current = handleSave

  const setupEditorListeners = (doc: Document, iframe: HTMLIFrameElement): void => {
    const paragraphs = doc.querySelectorAll<HTMLElement>('[data-paragraph-id]')
    paragraphs.forEach(paragraph => {
      paragraph.setAttribute('contenteditable', 'true')
      paragraph.setAttribute('spellcheck', 'false')
      paragraph.style.cursor = 'text'
      paragraph.style.minHeight = '1em'
    })

    const handleClick = (event: MouseEvent) => {
      const paragraph = findParagraphElement(event.target as Node)
      if (!paragraph) return
      const paragraphId = paragraph.dataset.paragraphId ?? null
      // Apply box-shadow immediately (sync) so the outline appears on first click
      // without waiting for the React re-render cycle.
      const allParagraphs = doc.querySelectorAll<HTMLElement>('[data-paragraph-id]')
      allParagraphs.forEach(p => { p.style.boxShadow = '' })
      paragraph.style.boxShadow = 'inset 0 0 0 2px rgba(59, 130, 246, 0.55)'
      activeParagraphIdRef.current = paragraphId
      setActiveParagraphId(paragraphId)
      requestAnimationFrame(() => {
        refreshPaletteFromSelection()
      })
    }

    const handleInput = (event: Event) => {
      const paragraph = findParagraphElement(event.target as Node)
      if (!paragraph) return
      syncDraftFromParagraph(paragraph)
    }

    const handleFocusOut = (event: FocusEvent) => {
      const paragraph = findParagraphElement(event.target as Node)
      if (!paragraph) return
      syncDraftFromParagraph(paragraph)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      const paragraph = findParagraphElement(event.target as Node)
      if (!paragraph) return

      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault()
        syncDraftFromParagraph(paragraph)
        void saveRef.current()
        return
      }

      if (event.key === 'Enter') {
        event.preventDefault()
        insertLineBreak(doc)
        syncDraftFromParagraph(paragraph)
        return
      }

      if (event.key === 'Backspace') {
        const isEmpty = paragraph.innerHTML.replace(/<br\s*\/?>/gi, '').trim() === ''
        if (isEmpty) {
          event.preventDefault()
          if (!window.confirm('삭제할까요?')) return
          const paragraphId = paragraph.dataset.paragraphId
          if (!paragraphId) return
          paragraph.style.display = 'none'
          setDraftTranslations(prev => ({ ...prev, [paragraphId]: '' }))
          setActiveParagraphId(null)
          setPalette(null)
        }
      }
    }

    const handlePaste = (event: ClipboardEvent) => {
      const paragraph = findParagraphElement(event.target as Node)
      if (!paragraph) return
      event.preventDefault()
      const text = event.clipboardData?.getData('text/plain') ?? ''
      insertPlainText(doc, text)
      syncDraftFromParagraph(paragraph)
    }

    const handleSelectionChange = () => {
      refreshPaletteFromSelection()
    }

    const handleMouseUp = () => {
      const selection = doc.getSelection()
      const paragraph = selection ? findSelectionParagraph(selection) : null
      const paragraphId = paragraph?.dataset.paragraphId ?? null
      if (paragraphId) {
        activeParagraphIdRef.current = paragraphId
        setActiveParagraphId(paragraphId)
      }
      refreshPaletteFromSelection()
    }

    const handleKeyUp = () => {
      refreshPaletteFromSelection()
    }

    const handleScroll = () => {
      refreshPaletteFromSelection()
    }

    doc.addEventListener('click', handleClick)
    doc.addEventListener('mouseup', handleMouseUp)
    doc.addEventListener('keyup', handleKeyUp)
    doc.addEventListener('input', handleInput)
    doc.addEventListener('focusout', handleFocusOut)
    doc.addEventListener('keydown', handleKeyDown)
    doc.addEventListener('paste', handlePaste)
    doc.addEventListener('selectionchange', handleSelectionChange)
    iframe.contentWindow?.addEventListener('scroll', handleScroll, { passive: true })

    cleanupRef.current = () => {
      doc.removeEventListener('click', handleClick)
      doc.removeEventListener('mouseup', handleMouseUp)
      doc.removeEventListener('keyup', handleKeyUp)
      doc.removeEventListener('input', handleInput)
      doc.removeEventListener('focusout', handleFocusOut)
      doc.removeEventListener('keydown', handleKeyDown)
      doc.removeEventListener('paste', handlePaste)
      doc.removeEventListener('selectionchange', handleSelectionChange)
      iframe.contentWindow?.removeEventListener('scroll', handleScroll)
    }
  }

  const setupViewerListeners = (doc: Document, chapterMapArg: Map<string, string>): void => {
    const handleClick = (event: MouseEvent) => {
      const a = (event.target as Element).closest?.('a[href]') as HTMLAnchorElement | null
      if (!a) return
      event.preventDefault()

      const href = a.getAttribute('href') ?? ''
      if (!href) return

      if (href.startsWith('#')) {
        const fragment = href.slice(1)
        const target =
          doc.getElementById(fragment) ??
          doc.querySelector(`[name="${CSS.escape(fragment)}"]`)
        target?.scrollIntoView({ block: 'start', behavior: 'auto' })
        return
      }

      const hashIdx = href.indexOf('#')
      const filePart = hashIdx >= 0 ? href.slice(0, hashIdx) : href
      const fragment = hashIdx >= 0 ? href.slice(hashIdx + 1) : null
      const basename = filePart.split('/').pop() ?? filePart

      const chapterId = chapterMapArg.get(basename)
      if (chapterId) {
        if (fragment) pendingFragmentRef.current = fragment
        setSelectedChapterId(chapterId)
      } else {
        window.open(href, '_blank', 'noopener,noreferrer')
      }
    }

    doc.addEventListener('click', handleClick)
    cleanupRef.current = () => {
      doc.removeEventListener('click', handleClick)
    }
  }

  const handleTranslationLoad = () => {
    cleanupRef.current?.()

    const iframe = translationRef.current
    const doc = iframe?.contentWindow?.document
    if (!iframe || !doc?.body) return  // mid-load guard

    if (isEditModeRef.current) {
      setupEditorListeners(doc, iframe)
    } else {
      setupViewerListeners(doc, chapterMap)
    }

    const pendingFragment = pendingFragmentRef.current
    if (pendingFragment) {
      pendingFragmentRef.current = null
      const target =
        doc.getElementById(pendingFragment) ??
        doc.querySelector(`[name="${CSS.escape(pendingFragment)}"]`)
      target?.scrollIntoView({ block: 'start', behavior: 'auto' })
    }
  }

  useEffect(() => {
    const iframe = translationRef.current
    const doc = iframe?.contentWindow?.document
    if (!iframe || !doc?.body) return  // iframe not yet loaded — handleTranslationLoad will handle it
    cleanupRef.current?.()
    if (isEditMode) {
      setupEditorListeners(doc, iframe)
    } else {
      setupViewerListeners(doc, chapterMap)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditMode, chapterContent?.chapter_id, chapterMap])

  const handleToggleEditMode = () => {
    if (isEditMode && hasUnsavedChanges) {
      if (!window.confirm('저장되지 않은 변경사항이 있습니다. 편집을 종료하면 변경사항이 사라집니다. 계속할까요?'))
        return
    }
    if (isEditMode) {
      // Editor → Viewer: sync ref first so handleTranslationLoad sees the new mode
      isEditModeRef.current = false
      setDiscardKey(k => k + 1)
      setDraftTranslations({})
      setActiveParagraphId(null)
      setPalette(null)
    }
    setIsEditMode(prev => !prev)
  }

  const confirmDiscardChanges = (): boolean => {
    if (!hasUnsavedChanges) return true
    return window.confirm('저장되지 않은 변경사항이 있습니다. 이동하면 내용이 사라집니다. 계속할까요?')
  }

  const handleChapterChange = (nextChapterId: string) => {
    if (nextChapterId === selectedChapterId) return
    if (!confirmDiscardChanges()) return
    setSelectedChapterId(nextChapterId)
  }

  const handleBackToListClick = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    if (!confirmDiscardChanges()) {
      event.preventDefault()
    }
  }

  const handleApplyStyle = (option: StyleOption | null) => {
    const iframe = translationRef.current
    const doc = iframe?.contentWindow?.document
    if (!doc || !palette) return
    if (!hasSelectionInsideParagraph(doc, palette.paragraphId)) return

    const changed = option === null ? doc.execCommand('removeFormat') : applyInlineStyle(doc, option)
    if (!changed) return

    const active = doc.querySelector<HTMLElement>(`[data-paragraph-id="${palette.paragraphId}"]`)
    if (active) {
      syncDraftFromParagraph(active)
    }
    refreshPaletteFromSelection()
  }

  const handleToggleSource = () => {
    if (!sourceAvailable || chapterLoading) return

    const fromRef = showSource ? sourceRef : translationRef
    const toRef = showSource ? translationRef : sourceRef
    const topParagraphId = getTopmostParagraphId(fromRef.current)

    setShowSource(prev => !prev)
    setPalette(null)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        scrollToParagraph(toRef.current, topParagraphId)
      })
    })
  }

  const formatChapterLabel = (chapter: JobChapter, index: number): string =>
    `${String(index + 1).padStart(chapterNumberWidth, '0')}. ${chapter.title}`

  if (loading) {
    return <p className="p-6 text-center text-sm text-muted-foreground">뷰어를 불러오는 중...</p>
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-3rem)] max-w-7xl flex-col overflow-hidden px-2 pb-2 pt-2 md:h-dvh md:px-4 md:pb-4 md:pt-4">
      <header className="sticky top-0 z-20 rounded-xl border bg-card/95 p-2 shadow-xs backdrop-blur supports-[backdrop-filter]:bg-card/75 md:p-3">
        {/* 행1: Back + filename + [편집/편집 중] + [저장 (n), 편집 모드만] */}
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="icon-xs" className="shrink-0">
            <Link to="/" aria-label="목록으로" onClick={handleBackToListClick}>
              <ChevronLeft className="size-4" />
            </Link>
          </Button>

          <p className="min-w-0 flex-1 truncate text-xs font-medium text-foreground/90 md:text-sm">
            {job?.filename}
          </p>

          <Button
            type="button"
            variant={isEditMode ? 'default' : 'outline'}
            size="xs"
            className="shrink-0"
            aria-pressed={isEditMode}
            onClick={handleToggleEditMode}
          >
            {isEditMode ? '편집 중' : '편집'}
          </Button>

          {isEditMode && (
            <Button
              type="button"
              variant={hasUnsavedChanges ? 'default' : 'outline'}
              size="xs"
              className="shrink-0"
              onClick={() => void handleSave()}
              disabled={!hasUnsavedChanges || chapterLoading || saving}
            >
              <Save className="size-3" />
              {saving ? '저장중' : `저장${hasUnsavedChanges ? ` (${pendingEdits.length})` : ''}`}
            </Button>
          )}
        </div>

        {/* 행2: 챕터 선택 + 원문/번역 토글 */}
        <div className="mt-2 flex items-center gap-2">
          <Select value={selectedChapterId} onValueChange={handleChapterChange}>
            <SelectTrigger size="sm" className="w-full min-w-0 bg-background text-xs md:text-sm">
              <SelectValue placeholder="챕터 선택" />
            </SelectTrigger>
            <SelectContent>
              {chapters.map((chapter, index) => (
                <SelectItem key={chapter.chapter_id} value={chapter.chapter_id}>
                  {formatChapterLabel(chapter, index)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant={showSource ? 'default' : 'outline'}
            size="xs"
            className="shrink-0"
            onClick={handleToggleSource}
            disabled={!sourceAvailable || chapterLoading}
          >
            <Languages className="size-3" />
            {showSource ? '번역' : '원문'}
          </Button>
        </div>
      </header>

      {error && (
        <Alert variant="destructive" className="mt-2">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {sourceMissing && (
        <Alert className="mt-2">
          <AlertDescription>원문 파일을 찾을 수 없습니다.</AlertDescription>
        </Alert>
      )}

      <section className="mt-2 min-h-0 flex-1 overflow-hidden rounded-xl border bg-card p-1 shadow-xs">
        {chapterLoading || !chapterContent ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            챕터를 불러오는 중...
          </div>
        ) : (
          <>
            <IframePanel
              key={`${selectedChapterId}-${discardKey}`}
              html={chapterContent.translation_html}
              hidden={showSource}
              iframeRef={translationRef}
              title="번역 보기"
              onLoad={handleTranslationLoad}
            />
            <IframePanel
              html={chapterContent.source_html ?? '<!doctype html><html><body></body></html>'}
              hidden={!showSource}
              iframeRef={sourceRef}
              title="원문 보기"
            />
          </>
        )}
      </section>

      {palette && !showSource && isEditMode && (
        <div
          className="fixed z-40 flex max-w-[92vw] items-center gap-1 rounded-lg border bg-background/95 p-1 shadow-md backdrop-blur"
          style={{ left: `${palette.left}px`, top: `${palette.top}px`, transform: 'translate(-50%, -100%)' }}
        >
          <Button type="button" size="xs" variant="outline" onMouseDown={e => e.preventDefault()} onClick={() => handleApplyStyle(null)}>
            기본 Aa
          </Button>
          {palette.options.length === 0 && (
            <p className="text-xs text-muted-foreground px-1">이 문단에는 인라인 서식이 없습니다</p>
          )}
          {palette.options.map(option => (
            <Button
              key={option.key}
              type="button"
              size="xs"
              variant="outline"
              onMouseDown={e => e.preventDefault()}
              onClick={() => handleApplyStyle(option)}
              style={option.previewStyle}
            >
              {option.label ?? 'Aa'}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
