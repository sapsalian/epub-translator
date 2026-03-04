import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, type JobInfo } from '../api/client'
import { Alert } from './ui/Alert'
import { Button } from './ui/Button'
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
        setInitialError('Failed to load jobs')
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
    return <p className="text-gray-500 text-center py-8">Loading jobs...</p>
  }

  if (initialError) {
    return (
      <div className="text-center py-8 space-y-2">
        <Alert variant="error">{initialError}</Alert>
        <Button variant="secondary" size="sm" onClick={() => { setInitialLoading(true); fetchJobs(true) }}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {pollUnstable && (
        <Alert variant="warning">Server connection is unstable. Retrying automatically...</Alert>
      )}
      {jobs.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No translation jobs yet.</p>
      ) : (
        jobs.map(job => (
          <JobCard key={job.job_id} job={job} onDeleted={() => fetchJobs(false)} />
        ))
      )}
    </div>
  )
}
