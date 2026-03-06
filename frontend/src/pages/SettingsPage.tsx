import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { apiClient, extractErrorMessage, type LanguageOption, type Settings } from '../api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [languages, setLanguages] = useState<LanguageOption[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [sourceLang, setSourceLang] = useState('')
  const [targetLang, setTargetLang] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)

  const loadSettings = async () => {
    setLoadError(null)
    try {
      const [s, langs] = await Promise.all([apiClient.getSettings(), apiClient.getLanguages()])
      setSettings(s)
      setLanguages(langs)
      setSourceLang(s.source_language)
      setTargetLang(s.target_language)
    } catch (err) {
      setLoadError(extractErrorMessage(err))
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const updated = await apiClient.updateSettings({
        model: settings.model,
        source_language: sourceLang,
        target_language: targetLang,
        ...(apiKey ? { openai_api_key: apiKey } : {}),
      })
      setSettings(updated)
      setApiKey('')
      toast.success('설정이 저장되었습니다.')
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loadError) {
    return (
      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-4">
        <Alert variant="destructive">
          <AlertDescription>설정을 불러오지 못했습니다: {loadError}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={loadSettings}>다시 시도</Button>
      </div>
    )
  }

  if (!settings) {
    return <p className="p-6 text-center text-sm text-muted-foreground">로딩 중...</p>
  }

  return (
    <div className="max-w-lg mx-auto p-4 md:p-6 space-y-6">
      {/* API 설정 섹션 */}
      <div className="space-y-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">API 설정</p>
          <Separator className="mt-1.5" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="api-key">OpenAI API Key</Label>
          <Input
            id="api-key"
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder={settings.api_key_set ? '이미 설정됨 — 변경하려면 입력' : 'sk-...'}
          />
        </div>
      </div>

      {/* 번역 기본값 섹션 */}
      <div className="space-y-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">번역 기본값</p>
          <Separator className="mt-1.5" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>기본 출발 언어</Label>
            <Select value={sourceLang} onValueChange={setSourceLang}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {languages.map(l => (
                  <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>기본 도착 언어</Label>
            <Select value={targetLang} onValueChange={setTargetLang}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {languages.map(l => (
                  <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <Button onClick={handleSave} disabled={saving}>
        {saving ? '저장 중...' : '저장'}
      </Button>
    </div>
  )
}
