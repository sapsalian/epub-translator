import { useEffect, useState } from 'react'
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

type ReaderPane = 'source' | 'translation'

function ParagraphHtml({ html, emptyMessage }: { html: string; emptyMessage?: string }) {
  if (!html) {
    return <p className="text-sm leading-7 text-muted-foreground">{emptyMessage ?? ''}</p>
  }

  return <div className="text-sm leading-7 [&_a]:text-primary [&_a]:underline [&_li]:ml-5 [&_ol]:ml-5 [&_ol]:list-decimal [&_p]:mb-0 [&_strong]:font-semibold [&_ul]:ml-5 [&_ul]:list-disc" dangerouslySetInnerHTML={{ __html: html }} />
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
  const [activePane, setActivePane] = useState<ReaderPane>('translation')

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
        const message = extractErrorMessage(err)
        setError(message)
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

  if (loading) {
    return <p className="p-6 text-center text-sm text-muted-foreground">뷰어를 불러오는 중...</p>
  }

  const sourceMissing = !!chapterContent && chapterContent.paragraphs.every(paragraph => paragraph.source === '')

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
              챕터를 선택해 원문과 번역본을 나란히 확인할 수 있습니다.
            </p>
          </div>

          <div className="flex items-center gap-2">
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
          </div>
        </div>

        <div className="flex gap-2 md:hidden">
          <Button
            variant={activePane === 'source' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setActivePane('source')}
          >
            원문
          </Button>
          <Button
            variant={activePane === 'translation' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setActivePane('translation')}
          >
            번역
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {chapterLoading || !chapterContent ? (
        <div className="rounded-2xl border bg-card p-8 text-center text-sm text-muted-foreground">
          챕터를 불러오는 중...
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-2">
          <section className={activePane === 'source' ? 'block' : 'hidden md:block'}>
            <div className="flex h-full flex-col overflow-hidden rounded-2xl border bg-card">
              <div className="flex items-center gap-2 border-b bg-muted/30 px-4 py-3">
                <Languages className="size-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">원문</h2>
              </div>
              <div className="flex-1 overflow-auto px-4 py-4">
                {sourceMissing && (
                  <Alert className="mb-4">
                    <AlertDescription>원문 파일을 찾을 수 없습니다.</AlertDescription>
                  </Alert>
                )}
                <div className="space-y-4">
                  {chapterContent.paragraphs.map(paragraph => (
                    <div key={paragraph.id} className="rounded-xl border border-transparent bg-background px-4 py-3">
                      <ParagraphHtml html={paragraph.source} emptyMessage={sourceMissing ? '' : '비어 있는 문단입니다.'} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className={activePane === 'translation' ? 'block' : 'hidden md:block'}>
            <div className="flex h-full flex-col overflow-hidden rounded-2xl border bg-card">
              <div className="flex items-center gap-2 border-b bg-primary/5 px-4 py-3">
                <Eye className="size-4 text-primary" />
                <h2 className="text-sm font-semibold">번역</h2>
              </div>
              <div className="flex-1 overflow-auto px-4 py-4">
                <div className="space-y-4">
                  {chapterContent.paragraphs.map(paragraph => (
                    <div key={paragraph.id} className="rounded-xl border border-primary/10 bg-primary/5 px-4 py-3">
                      <ParagraphHtml html={paragraph.translation} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
