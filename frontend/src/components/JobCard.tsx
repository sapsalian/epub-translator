import { useState } from 'react'
import { Link } from 'react-router-dom'

declare global {
  interface Window {
    pywebview?: { api: { download: (token: string, filename: string) => Promise<boolean> } }
  }
}
import { Download, RotateCcw, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import type { JobInfo } from '../api/client'
import { apiClient } from '../api/client'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

const stateVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  queued: 'secondary',
  processing: 'default',
  done: 'outline',
  failed: 'destructive',
  awaiting_review: 'secondary',
}

const stateLabel: Record<string, string> = {
  queued: '대기 중',
  processing: '번역 중',
  done: '완료',
  failed: '실패',
  awaiting_review: '검토 필요',
}

const stageLabel: Record<string, string> = {
  EXTRACTING: '파일 분석 중',
  PREPROCESSING: '사전 처리 중',
  TRANSLATING: '번역 중',
  INSERTING: '파일 생성 중',
  extracting: '파일 분석 중',
  preprocessing: '사전 처리 중',
  translating: '번역 중',
  inserting: '파일 생성 중',
  awaiting_review: '용어집 검토 대기',
  done: '완료',
}

const accentColor: Record<string, string> = {
  queued: 'bg-muted-foreground/50',
  processing: 'bg-primary',
  done: 'bg-success',
  failed: 'bg-destructive',
  awaiting_review: 'bg-warning',
}

interface JobCardProps {
  job: JobInfo
  onDeleted: () => void
}

export function JobCard({ job, onDeleted }: JobCardProps) {
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)

  const handleDownload = async () => {
    if (!job.download_token) return
    if (window.pywebview) {
      await window.pywebview.api.download(job.download_token, job.filename)
    } else {
      const a = document.createElement('a')
      a.href = `/download/${job.download_token}`
      a.download = ''
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await apiClient.deleteJob(job.job_id)
      onDeleted()
    } catch {
      toast.error('작업을 삭제하지 못했습니다.')
    } finally {
      setDeleting(false)
    }
  }

  const showProgress = job.state === 'processing'
  const isActiveJob = job.state === 'queued' || job.state === 'processing'

  return (
    <div className="relative flex flex-col gap-1 px-4 py-3 group">
      {/* Left accent bar */}
      <div className={cn('absolute left-0 inset-y-2 w-0.5 rounded-full', accentColor[job.state] ?? 'bg-muted-foreground/50')} />

      {/* Main row */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="flex-1 text-sm font-medium truncate">{job.filename}</span>

        {job.state === 'processing' && job.stage && (
          <span className="text-xs text-muted-foreground shrink-0">
            {stageLabel[job.stage] ?? job.stage}
          </span>
        )}

        {job.state === 'queued' && job.queue_position != null && (
          <span className="text-xs text-muted-foreground shrink-0">#{job.queue_position}</span>
        )}

        <Badge variant={stateVariant[job.state] ?? 'secondary'} className="shrink-0 text-xs">
          {stateLabel[job.state] ?? job.state}
        </Badge>

        {/* Hover actions */}
        <div className="flex items-center gap-1 md:opacity-0 md:group-hover:opacity-100 transition-opacity shrink-0">
          {job.state === 'awaiting_review' && (
            <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
              <Link to={`/jobs/${job.job_id}/review/glossary`}>검토</Link>
            </Button>
          )}
          {job.state === 'done' && job.download_token && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleDownload}>
              <Download size={13} />
            </Button>
          )}
          {job.state === 'failed' && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-primary"
              disabled={retrying}
              onClick={async () => {
                setRetrying(true)
                try {
                  await apiClient.retryJob(job.job_id)
                } catch {
                  toast.error('재시도에 실패했습니다.')
                } finally {
                  setRetrying(false)
                }
              }}
            >
              <RotateCcw size={13} />
            </Button>
          )}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                disabled={deleting}
              >
                <Trash2 size={13} />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>작업을 삭제할까요?</AlertDialogTitle>
                <AlertDialogDescription>
                  {isActiveJob
                    ? '현재 진행 중인 작업입니다. 삭제하면 번역이 중단되며 복구할 수 없습니다.'
                    : '삭제하면 작업 기록이 제거됩니다. 이 작업은 되돌릴 수 없습니다.'}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>취소</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  삭제
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Progress row */}
      {showProgress && (
        <div className="flex items-center gap-2">
          <Progress value={job.progress * 100} className="h-1 flex-1" />
          <span className="text-xs text-muted-foreground shrink-0 tabular-nums">
            {Math.round(job.progress * 100)}%
          </span>
        </div>
      )}

      {/* Error message */}
      {job.state === 'failed' && job.error && (
        <p className="text-xs text-destructive">{job.error}</p>
      )}
    </div>
  )
}
