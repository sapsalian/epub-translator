import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Eye, Languages } from 'lucide-react'
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
}

function IframePanel({ html, hidden, iframeRef }: IframePanelProps) {
  const [height, setHeight] = useState(0)
  const resizeObserverRef = useRef<ResizeObserver | null>(null)

  const updateHeight = () => {
    const doc = iframeRef.current?.contentWindow?.document
    if (!doc?.body) return
    setHeight(doc.body.scrollHeight)
  }

  const handleLoad = () => {
    resizeObserverRef.current?.disconnect()
    resizeObserverRef.current = null

    const doc = iframeRef.current?.contentWindow?.document
    if (!doc?.body) return

    const observer = new ResizeObserver(() => {
      updateHeight()
    })
    observer.observe(doc.body)
    resizeObserverRef.current = observer
    updateHeight()
  }

  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect()
      resizeObserverRef.current = null
    }
  }, [])

  return (
    <iframe
      ref={iframeRef}
      srcDoc={html}
      onLoad={handleLoad}
      sandbox="allow-same-origin"
      style={{
        width: '100%',
        border: 'none',
        display: hidden ? 'none' : 'block',
        height: `${Math.max(height, 480)}px`,
        background: 'white',
      }}
      title={hidden ? 'source-hidden' : 'viewer-visible'}
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

  useEffect(() => {
    if (!sourceAvailable && showSource) {
      setShowSource(false)
    }
  }, [showSource, sourceAvailable])

  const handleToggleSource = () => {
    if (!sourceAvailable) return

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

  if (loading) {
    return <p className="p-6 text-center text-sm text-muted-foreground">뷰어를 불러오는 중...</p>
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-xs">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <Button asChild variant="ghost" size="sm" className="w-fit px-0 text-muted-foreground">
              <Link to="/">
                <ChevronLeft className="size-4" />
                목록으로
              </Link>
            </Button>
            <h1 className="text-lg font-semibold">{job?.filename}</h1>
            <p className="text-sm text-muted-foreground">
              EPUB 원본 스타일 그대로 확인할 수 있습니다.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Eye className="size-4 text-muted-foreground" />
            <Select value={selectedChapterId} onValueChange={setSelectedChapterId}>
              <SelectTrigger className="w-full min-w-64 bg-background md:w-80">
                <SelectValue placeholder="챕터 선택" />
              </SelectTrigger>
              <SelectContent>
                {chapters.map(chapter => (
                  <SelectItem key={chapter.chapter_id} value={chapter.chapter_id}>
                    {chapter.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant={showSource ? 'default' : 'outline'}
              onClick={handleToggleSource}
              disabled={!sourceAvailable || chapterLoading}
            >
              <Languages className="size-4" />
              {showSource ? '번역 보기' : '원문 보기'}
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!sourceAvailable && !chapterLoading && (
        <Alert>
          <AlertDescription>원문 파일을 찾을 수 없습니다.</AlertDescription>
        </Alert>
      )}

      {chapterLoading || !chapterContent ? (
        <div className="rounded-2xl border bg-card p-8 text-center text-sm text-muted-foreground">
          챕터를 불러오는 중...
        </div>
      ) : (
        <div className="rounded-2xl border bg-card p-2 shadow-xs">
          <IframePanel
            html={chapterContent.translation_html}
            hidden={showSource}
            iframeRef={translationRef}
          />
          <IframePanel
            html={chapterContent.source_html ?? '<!doctype html><html><body></body></html>'}
            hidden={!showSource}
            iframeRef={sourceRef}
          />
        </div>
      )}
    </div>
  )
}
