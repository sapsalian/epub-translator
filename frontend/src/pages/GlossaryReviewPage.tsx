import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { apiClient, extractErrorMessage, type GlossaryTerm } from '../api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

function normalizeTerms(terms: GlossaryTerm[]): GlossaryTerm[] {
  return terms
    .map(term => ({ source: term.source.trim(), target: term.target.trim() }))
    .filter(term => term.source.length > 0 || term.target.length > 0)
}

export function GlossaryReviewPage() {
  const { id: jobId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [continuing, setContinuing] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await apiClient.getJobGlossary(jobId)
        setTerms(data.terms)
      } catch (err) {
        setError(extractErrorMessage(err))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [jobId])

  const validationError = useMemo(() => {
    const normalized = normalizeTerms(terms)
    const seen = new Set<string>()
    for (const term of normalized) {
      if (!term.source || !term.target) {
        return 'source/target를 모두 입력해 주세요.'
      }
      if (seen.has(term.source)) {
        return `중복 source 용어가 있습니다: ${term.source}`
      }
      seen.add(term.source)
    }
    return null
  }, [terms])

  const save = async () => {
    if (!jobId) return false
    if (validationError) {
      setError(validationError)
      return false
    }

    setSaving(true)
    setError(null)
    try {
      const normalized = normalizeTerms(terms)
      await apiClient.updateJobGlossary(jobId, normalized)
      setDirty(false)
      toast.success('단어집을 저장했습니다.')
      return true
    } catch (err) {
      setError(extractErrorMessage(err))
      return false
    } finally {
      setSaving(false)
    }
  }

  const onContinue = async () => {
    if (!jobId) return
    setContinuing(true)
    const saved = await save()
    if (!saved) {
      setContinuing(false)
      return
    }

    try {
      await apiClient.continueJob(jobId)
      toast.success('번역을 재개했습니다.')
      navigate('/')
    } catch (err) {
      setError(extractErrorMessage(err))
      setContinuing(false)
    }
  }

  if (loading) {
    return <p className="p-6 text-center text-sm text-muted-foreground">로딩 중...</p>
  }

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-4">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">단어집 검토</h1>
        <p className="text-sm text-muted-foreground">용어를 수정/추가/삭제한 후 진행을 누르면 번역이 시작됩니다.</p>
      </div>

      {dirty && (
        <Alert>
          <AlertDescription>저장되지 않은 변경사항이 있습니다.</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="rounded-lg border overflow-hidden">
        <div className="grid grid-cols-[1fr_1fr_auto] gap-2 p-3 bg-muted/40 text-xs font-medium">
          <span>Source</span>
          <span>Target</span>
          <span>Action</span>
        </div>
        <div className="divide-y">
          {terms.map((term, index) => (
            <div key={`${index}-${term.source}`} className="grid grid-cols-[1fr_1fr_auto] gap-2 p-3">
              <Input
                value={term.source}
                onChange={e => {
                  const next = [...terms]
                  next[index] = { ...next[index], source: e.target.value }
                  setTerms(next)
                  setDirty(true)
                }}
                placeholder="source term"
              />
              <Input
                value={term.target}
                onChange={e => {
                  const next = [...terms]
                  next[index] = { ...next[index], target: e.target.value }
                  setTerms(next)
                  setDirty(true)
                }}
                placeholder="target term"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setTerms(terms.filter((_, i) => i !== index))
                  setDirty(true)
                }}
              >
                삭제
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          onClick={() => {
            setTerms([...terms, { source: '', target: '' }])
            setDirty(true)
          }}
        >
          용어 추가
        </Button>
        <Button variant="outline" onClick={save} disabled={saving || continuing}>
          {saving ? '저장 중...' : '저장'}
        </Button>
        <Button onClick={onContinue} disabled={saving || continuing || !!validationError}>
          {continuing ? '진행 중...' : '진행'}
        </Button>
      </div>
    </div>
  )
}
