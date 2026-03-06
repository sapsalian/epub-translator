import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, type JobInfo } from '../api/client'

const POLL_INTERVAL_MS = 5000
const POLL_FAILURE_THRESHOLD = 3

export function useJobUpdates(refreshKey: number) {
  const [jobs, setJobs] = useState<JobInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const sseRef = useRef<EventSource | null>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const consecutiveFailures = useRef(0)
  const usingSse = useRef(false)

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }, [])

  const fetchJobs = useCallback(async (isInitial = false) => {
    try {
      const data = await apiClient.listJobs()
      setJobs(data)
      consecutiveFailures.current = 0
      setIsConnected(true)
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
        if (consecutiveFailures.current >= POLL_FAILURE_THRESHOLD) {
          setIsConnected(false)
        }
      }
    }
  }, [])

  const startPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) return
    fetchJobs(true)
    pollIntervalRef.current = setInterval(() => fetchJobs(false), POLL_INTERVAL_MS)
  }, [fetchJobs])

  const startSSE = useCallback(() => {
    sseRef.current?.close()
    usingSse.current = false

    const es = new EventSource('/api/jobs/stream')
    sseRef.current = es

    es.onopen = () => {
      usingSse.current = true
      setIsConnected(true)
      setError(null)
      stopPolling()
    }

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as JobInfo[]
        setJobs(data)
        setLoading(false)
      } catch {
        // ignore malformed events
      }
    }

    es.onerror = () => {
      es.close()
      usingSse.current = false
      setIsConnected(false)
      startPolling()
    }
  }, [stopPolling, startPolling])

  useEffect(() => {
    startSSE()
    return () => {
      sseRef.current?.close()
      stopPolling()
    }
  }, [startSSE, stopPolling, refreshKey])

  const refresh = useCallback(() => {
    if (usingSse.current) {
      // SSE 연결 중이면 재연결로 최신 상태 즉시 수신
      startSSE()
    } else {
      fetchJobs(false)
    }
  }, [startSSE, fetchJobs])

  const retry = useCallback(() => {
    setLoading(true)
    setError(null)
    startSSE()
  }, [startSSE])

  return { jobs, loading, error, isConnected, refresh, retry }
}
