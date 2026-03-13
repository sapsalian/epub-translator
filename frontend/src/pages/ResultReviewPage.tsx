import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Languages } from 'lucide-react'
import { toast } from 'sonner'

import {
  apiClient,
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
  iframeRef: React.RefObject<HTMLIFrameElement | null>
  title: string
}

function IframePanel({ html, hidden, iframeRef, title }: IframePanelProps) {
  return (
    <iframe
      ref={iframeRef}
      srcDoc={html}
      sandbox="allow-same-origin"
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
  const [showSource, setShowSource] = useState(false)

  const translationRef = useRef<HTMLIFrameElement>(null)
  const sourceRef = useRef<HTMLIFrameElement>(null)

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

  const sourceAvailable = chapterContent?.source_html != null
  const sourceMissing = !sourceAvailable && !chapterLoading && !!chapterContent
  const chapterNumberWidth = Math.max(2, String(chapters.length || 1).length)

  useEffect(() => {
    if (!sourceAvailable && showSource) {
      setShowSource(false)
    }
  }, [showSource, sourceAvailable])

  const handleToggleSource = () => {
    if (!sourceAvailable || chapterLoading) return

    const fromRef = showSource ? sourceRef : translationRef
    const toRef = showSource ? translationRef : sourceRef
    const topParagraphId = getTopmostParagraphId(fromRef.current)

    setShowSource(prev => !prev)
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
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="icon-xs" className="shrink-0">
            <Link to="/" aria-label="목록으로">
              <ChevronLeft className="size-4" />
            </Link>
          </Button>

          <p className="min-w-0 flex-1 truncate text-xs font-medium text-foreground/90 md:text-sm">
            {job?.filename}
          </p>

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

        <div className="mt-2 flex items-center gap-2">
          <Select value={selectedChapterId} onValueChange={setSelectedChapterId}>
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
          <span className="shrink-0 text-[10px] text-muted-foreground md:text-xs">
            {showSource ? '원문' : '번역'}
          </span>
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
              html={chapterContent.translation_html}
              hidden={showSource}
              iframeRef={translationRef}
              title="번역 보기"
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
    </div>
  )
}
