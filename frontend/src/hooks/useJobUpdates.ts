import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, type JobInfo } from '../api/client'

const POLL_FAILURE_THRESHOLD = 3

export function useJobUpdates(refreshKey: number) {
  const [jobs, setJobs] = useState<JobInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pollUnstable, setPollUnstable] = useState(false)
  const consecutiveFailures = useRef(0)

  const fetchJobs = useCallback(async (isInitial = false) => {
    try {
      const data = await apiClient.listJobs()
      setJobs(data)
      consecutiveFailures.current = 0
      setPollUnstable(false)
      if (isInitial) {
        setError(null)
        setLoading(false)
      }
    } catch {
      if (isInitial) {
        setError('작업 목록을 불러오지 못했습니다.')
        setLoading(false)
      } else {
        consecutiveFailures.current++
        if (consecutiveFailures.current >= POLL_FAILURE_THRESHOLD) setPollUnstable(true)
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

  const refresh = useCallback(() => fetchJobs(false), [fetchJobs])

  const retry = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchJobs(true)
  }, [fetchJobs])

  return { jobs, loading, error, isConnected: !pollUnstable, refresh, retry }
}
