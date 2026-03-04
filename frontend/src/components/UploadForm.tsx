import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, extractErrorMessage, type LanguageOption } from '../api/client'
import { Alert } from './ui/Alert'
import { Button } from './ui/Button'

interface UploadFormProps {
  onJobCreated: () => void
}

export function UploadForm({ onJobCreated }: UploadFormProps) {
  const [languages, setLanguages] = useState<LanguageOption[]>([])
  const [langError, setLangError] = useState<string | null>(null)
  const [sourceLang, setSourceLang] = useState('')
  const [targetLang, setTargetLang] = useState('')
  const [customInstructions, setCustomInstructions] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const loadLanguages = useCallback(async () => {
    setLangError(null)
    try {
      const langs = await apiClient.getLanguages()
      setLanguages(langs)
      if (langs.length > 0) {
        setSourceLang(langs[0].code)
        setTargetLang(langs.length > 1 ? langs[1].code : langs[0].code)
      }
    } catch (err) {
      setLangError(extractErrorMessage(err))
    }
  }, [])

  useEffect(() => {
    loadLanguages()
  }, [loadLanguages])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.name.endsWith('.epub')) setFile(dropped)
  }, [])

  const handleSubmit = async () => {
    if (!file || !sourceLang || !targetLang) return
    setLoading(true)
    setSubmitError(null)
    try {
      const { upload_id } = await apiClient.uploadFile(file)
      await apiClient.createJob({
        upload_id,
        source_language: sourceLang,
        target_language: targetLang,
        custom_instructions: customInstructions || undefined,
      })
      setFile(null)
      setCustomInstructions('')
      if (inputRef.current) inputRef.current.value = ''
      onJobCreated()
    } catch (err) {
      setSubmitError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".epub"
          className="hidden"
          onChange={e => { if (e.target.files?.[0]) setFile(e.target.files[0]) }}
        />
        {file ? (
          <p className="text-gray-700">{file.name}</p>
        ) : (
          <p className="text-gray-500">Drop an EPUB file here or click to select</p>
        )}
      </div>

      {langError ? (
        <Alert variant="error">
          Failed to load languages: {langError}
          <button className="ml-2 underline" onClick={loadLanguages}>Retry</button>
        </Alert>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1">
            <span className="text-sm font-medium">Source Language</span>
            <select
              className="w-full border rounded px-3 py-2"
              value={sourceLang}
              onChange={e => setSourceLang(e.target.value)}
            >
              {languages.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Target Language</span>
            <select
              className="w-full border rounded px-3 py-2"
              value={targetLang}
              onChange={e => setTargetLang(e.target.value)}
            >
              {languages.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </label>
        </div>
      )}

      <label className="block space-y-1">
        <span className="text-sm font-medium">Custom Instructions (optional)</span>
        <textarea
          className="w-full border rounded px-3 py-2 h-20 resize-none"
          value={customInstructions}
          onChange={e => setCustomInstructions(e.target.value)}
          placeholder="Additional instructions for translation..."
        />
      </label>

      {submitError && <Alert variant="error">{submitError}</Alert>}

      <Button onClick={handleSubmit} disabled={!file || loading || !!langError}>
        {loading ? 'Uploading...' : 'Start Translation'}
      </Button>
    </div>
  )
}
