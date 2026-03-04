import { useState } from 'react'
import type { JobInfo } from '../api/client'
import { apiClient, extractErrorMessage } from '../api/client'
import { Alert } from './ui/Alert'
import { Badge } from './ui/Badge'
import { Button } from './ui/Button'
import { Progress } from './ui/Progress'

const stateVariant: Record<JobInfo['state'], 'default' | 'success' | 'warning' | 'danger'> = {
  queued: 'default',
  processing: 'warning',
  done: 'success',
  failed: 'danger',
}

const stateLabel: Record<JobInfo['state'], string> = {
  queued: 'Queued',
  processing: 'Processing',
  done: 'Done',
  failed: 'Failed',
}

interface JobCardProps {
  job: JobInfo
  onDeleted: () => void
}

export function JobCard({ job, onDeleted }: JobCardProps) {
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const handleDelete = async () => {
    setDeleting(true)
    setDeleteError(null)
    try {
      await apiClient.deleteJob(job.job_id)
      onDeleted()
    } catch (err) {
      setDeleteError(extractErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-medium truncate mr-2">{job.filename}</span>
        <Badge variant={stateVariant[job.state]}>{stateLabel[job.state]}</Badge>
      </div>

      {job.state === 'queued' && job.queue_position != null && (
        <p className="text-sm text-gray-500">Queue position: {job.queue_position}</p>
      )}

      {(job.state === 'processing' || job.state === 'done') && (
        <div className="space-y-1">
          <Progress value={job.progress * 100} />
          <p className="text-xs text-gray-500">{job.stage} - {Math.round(job.progress * 100)}%</p>
        </div>
      )}

      {job.state === 'failed' && job.error && (
        <p className="text-sm text-red-600">{job.error}</p>
      )}

      {deleteError && <Alert variant="error">{deleteError}</Alert>}

      <div className="flex gap-2 pt-1">
        {job.state === 'done' && job.download_token && (
          <a href={`/download/${job.download_token}`} download>
            <Button size="sm">Download</Button>
          </a>
        )}
        <Button variant="danger" size="sm" onClick={handleDelete} disabled={deleting}>
          {deleting ? 'Deleting...' : 'Delete'}
        </Button>
      </div>
    </div>
  )
}
