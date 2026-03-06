import { useState } from 'react'
import { Download, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import type { JobInfo } from '../api/client'
import { apiClient } from '../api/client'
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
  queued: 'Queued',
  processing: 'Processing',
  done: 'Done',
  failed: 'Failed',
  awaiting_review: 'Review',
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

  const showProgress = job.state === 'processing' || job.state === 'done'

  return (
    <div className="relative flex flex-col gap-1 px-4 py-3 group">
      {/* Left accent bar */}
      <div className={cn('absolute left-0 inset-y-2 w-0.5 rounded-full', accentColor[job.state] ?? 'bg-muted-foreground/50')} />

      {/* Main row */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="flex-1 text-sm font-medium truncate">{job.filename}</span>

        {job.state === 'processing' && job.stage && (
          <span className="text-xs text-muted-foreground shrink-0">{job.stage}</span>
        )}

        {job.state === 'queued' && job.queue_position != null && (
          <span className="text-xs text-muted-foreground shrink-0">#{job.queue_position}</span>
        )}

        <Badge variant={stateVariant[job.state] ?? 'secondary'} className="shrink-0 text-xs">
          {stateLabel[job.state] ?? job.state}
        </Badge>

        {/* Hover actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          {job.state === 'done' && job.download_token && (
            <a href={`/download/${job.download_token}`} download>
              <Button variant="ghost" size="icon" className="h-7 w-7">
                <Download size={13} />
              </Button>
            </a>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={handleDelete}
            disabled={deleting}
          >
            <Trash2 size={13} />
          </Button>
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
