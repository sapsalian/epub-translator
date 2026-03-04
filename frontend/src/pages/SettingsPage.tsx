import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient, extractErrorMessage, type LanguageOption, type Settings } from '../api/client'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [languages, setLanguages] = useState<LanguageOption[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [model, setModel] = useState('')
  const [sourceLang, setSourceLang] = useState('')
  const [targetLang, setTargetLang] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const loadSettings = async () => {
    setLoadError(null)
    try {
      const [s, langs] = await Promise.all([apiClient.getSettings(), apiClient.getLanguages()])
      setSettings(s)
      setLanguages(langs)
      setModel(s.model)
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
    setSaving(true)
    setSaved(false)
    setSaveError(null)
    try {
      const updated = await apiClient.updateSettings({
        model,
        source_language: sourceLang,
        target_language: targetLang,
        ...(apiKey ? { openai_api_key: apiKey } : {}),
      })
      setSettings(updated)
      setApiKey('')
      setSaved(true)
    } catch (err) {
      setSaveError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loadError) {
    return (
      <div className="max-w-lg mx-auto p-6 space-y-4">
        <Alert variant="error">Failed to load settings: {loadError}</Alert>
        <Button variant="secondary" onClick={loadSettings}>Retry</Button>
      </div>
    )
  }

  if (!settings) return <div className="p-6 text-center text-gray-500">Loading...</div>

  return (
    <div className="max-w-lg mx-auto p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/" className="text-blue-600 hover:underline text-sm">&larr; Back</Link>
        <h1 className="text-2xl font-bold">Settings</h1>
      </div>

      <label className="block space-y-1">
        <span className="text-sm font-medium">OpenAI API Key</span>
        <input
          type="password"
          className="w-full border rounded px-3 py-2"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder={settings.api_key_set ? 'API key is set (enter new to replace)' : 'Enter your API key'}
        />
        {settings.api_key_set && !apiKey && (
          <p className="text-xs text-green-600">API key is configured.</p>
        )}
      </label>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Model</span>
        <input
          type="text"
          className="w-full border rounded px-3 py-2"
          value={model}
          onChange={e => setModel(e.target.value)}
        />
      </label>

      <div className="grid grid-cols-2 gap-4">
        <label className="space-y-1">
          <span className="text-sm font-medium">Default Source Language</span>
          <select
            className="w-full border rounded px-3 py-2"
            value={sourceLang}
            onChange={e => setSourceLang(e.target.value)}
          >
            {languages.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Default Target Language</span>
          <select
            className="w-full border rounded px-3 py-2"
            value={targetLang}
            onChange={e => setTargetLang(e.target.value)}
          >
            {languages.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </label>
      </div>

      {saveError && <Alert variant="error">{saveError}</Alert>}

      <div className="flex items-center gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
        {saved && <span className="text-sm text-green-600">Settings saved.</span>}
      </div>
    </div>
  )
}
