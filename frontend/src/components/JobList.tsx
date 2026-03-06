import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useJobUpdates } from '../hooks/useJobUpdates'
import { JobCard } from './JobCard'

interface JobListProps {
  refreshKey: number
}

export function JobList({ refreshKey }: JobListProps) {
  const { jobs, loading, error, isConnected, refresh, retry } = useJobUpdates(refreshKey)

  if (loading) {
    return <p className="text-muted-foreground text-center py-8 text-sm">로딩 중...</p>
  }

  if (error) {
    return (
      <div className="text-center py-8 space-y-2">
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" size="sm" onClick={retry}>
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
          <div className={cn('w-1.5 h-1.5 rounded-full', isConnected ? 'bg-success' : 'bg-warning')} />
          <span className="text-xs text-muted-foreground">
            {isConnected ? '연결됨' : '연결 불안정'}
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
            <JobCard key={job.job_id} job={job} onDeleted={refresh} />
          ))}
        </div>
      )}
    </div>
  )
}
