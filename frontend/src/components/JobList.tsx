import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, type JobInfo } from '../api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { JobCard } from './JobCard'

const POLL_FAILURE_THRESHOLD = 3

interface JobListProps {
  refreshKey: number
}

export function JobList({ refreshKey }: JobListProps) {
  const [jobs, setJobs] = useState<JobInfo[]>([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [initialError, setInitialError] = useState<string | null>(null)
  const [pollUnstable, setPollUnstable] = useState(false)
  const consecutiveFailures = useRef(0)

  const fetchJobs = useCallback(async (isInitial = false) => {
    try {
      const data = await apiClient.listJobs()
      setJobs(data)
      consecutiveFailures.current = 0
      setPollUnstable(false)
      if (isInitial) {
        setInitialError(null)
        setInitialLoading(false)
      }
    } catch {
      if (isInitial) {
        setInitialError('작업 목록을 불러오지 못했습니다.')
        setInitialLoading(false)
      } else {
        consecutiveFailures.current++
        if (consecutiveFailures.current >= POLL_FAILURE_THRESHOLD) {
          setPollUnstable(true)
        }
      }
    }
  }, [])

  useEffect(() => {
    fetchJobs(true)
  }, [fetchJobs, refreshKey])

  useEffect(() => {
    const id = setInterval(() => fetchJobs(false), 5000)
    return () => clearInterval(id)
  }, [fetchJobs])

  if (initialLoading) {
    return <p className="text-muted-foreground text-center py-8 text-sm">로딩 중...</p>
  }

  if (initialError) {
    return (
      <div className="text-center py-8 space-y-2">
        <Alert variant="destructive">
          <AlertDescription>{initialError}</AlertDescription>
        </Alert>
        <Button variant="outline" size="sm" onClick={() => { setInitialLoading(true); fetchJobs(true) }}>
          다시 시도
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          번역 작업{jobs.length > 0 && ` (${jobs.length})`}
        </span>
        <div className="flex items-center gap-1.5">
          <div className={cn('w-1.5 h-1.5 rounded-full', pollUnstable ? 'bg-warning' : 'bg-success')} />
          <span className="text-xs text-muted-foreground">
            {pollUnstable ? '연결 불안정' : '연결됨'}
          </span>
        </div>
      </div>

      {/* Job list */}
      {jobs.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-sm text-muted-foreground">아직 번역 작업이 없습니다</p>
          <p className="text-xs text-muted-foreground mt-1">위에서 EPUB 파일을 업로드해서 번역을 시작하세요</p>
        </div>
      ) : (
        <div className="divide-y divide-border rounded-lg border overflow-hidden">
          {jobs.map(job => (
            <JobCard key={job.job_id} job={job} onDeleted={() => fetchJobs(false)} />
          ))}
        </div>
      )}
    </div>
  )
}
