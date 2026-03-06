import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, Settings as SettingsIcon, X } from 'lucide-react'
import { apiClient, extractErrorMessage, type LanguageOption } from '../api/client'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'

interface UploadFormProps {
  onJobCreated: () => void
}

export function UploadForm({ onJobCreated }: UploadFormProps) {
  const [languages, setLanguages] = useState<LanguageOption[]>([])
  const [sourceLang, setSourceLang] = useState('')
  const [targetLang, setTargetLang] = useState('')
  const [customInstructions, setCustomInstructions] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const init = async () => {
      const [settingsResult, langsResult] = await Promise.allSettled([
        apiClient.getSettings(),
        apiClient.getLanguages(),
      ])

      const langs = langsResult.status === 'fulfilled' ? langsResult.value : []
      setLanguages(langs)

      let defaultSource = langs[0]?.code ?? ''
      let defaultTarget = langs[1]?.code ?? langs[0]?.code ?? ''

      if (settingsResult.status === 'fulfilled') {
        const { source_language, target_language } = settingsResult.value
        if (source_language && langs.some(l => l.code === source_language)) {
          defaultSource = source_language
        }
        if (target_language && langs.some(l => l.code === target_language)) {
          defaultTarget = target_language
        }
      }

      setSourceLang(defaultSource)
      setTargetLang(defaultTarget)
    }
    init()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.name.endsWith('.epub')) setFile(dropped)
  }, [])

  const clearFile = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
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
    <div className="space-y-1">
      <div
        className={`flex flex-col md:flex-row md:items-center gap-2 p-2 rounded-lg border transition-colors ${dragOver ? 'border-primary bg-primary/5' : 'border-border bg-background'}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".epub"
          className="hidden"
          onChange={e => { if (e.target.files?.[0]) setFile(e.target.files[0]) }}
        />

        {/* Row 1: Drop zone + mobile settings button */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div
            className="flex flex-1 min-w-0 items-center gap-1.5 px-1 cursor-pointer"
            onClick={() => inputRef.current?.click()}
          >
            <FileText size={14} className={file ? 'text-foreground shrink-0' : 'text-muted-foreground shrink-0'} />
            <span className={`text-sm truncate ${file ? 'text-foreground' : 'text-muted-foreground'}`}>
              {file ? file.name : 'EPUB 파일 드롭 또는 클릭'}
            </span>
            {file && (
              <button
                type="button"
                onClick={clearFile}
                className="ml-auto shrink-0 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Settings button (mobile only) */}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 md:hidden"
            onClick={() => setSheetOpen(true)}
          >
            <SettingsIcon size={14} />
          </Button>
        </div>

        {/* Row 2 (mobile) / continuation (desktop): language selects + settings + submit */}
        <div className="flex items-center gap-2">
          <Select value={sourceLang} onValueChange={setSourceLang}>
            <SelectTrigger className="flex-1 md:flex-none md:w-28 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map(l => (
                <SelectItem key={l.code} value={l.code} className="text-xs">{l.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <span className="text-xs text-muted-foreground shrink-0">→</span>

          <Select value={targetLang} onValueChange={setTargetLang}>
            <SelectTrigger className="flex-1 md:flex-none md:w-28 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map(l => (
                <SelectItem key={l.code} value={l.code} className="text-xs">{l.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Settings button (desktop only) */}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 hidden md:inline-flex"
            onClick={() => setSheetOpen(true)}
          >
            <SettingsIcon size={14} />
          </Button>

          <Button
            size="sm"
            className="shrink-0"
            onClick={handleSubmit}
            disabled={!file || loading || languages.length === 0}
          >
            {loading ? '업로드 중...' : '번역 →'}
          </Button>
        </div>
      </div>

      {/* Sheet controlled via state (no SheetTrigger needed) */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>번역 설정</SheetTitle>
          </SheetHeader>
          <div className="mt-6 space-y-3 px-1">
            <Label>지시사항 (선택)</Label>
            <Textarea
              value={customInstructions}
              onChange={e => setCustomInstructions(e.target.value)}
              placeholder="번역에 대한 추가 지시사항..."
              className="h-32 resize-none text-sm"
            />
          </div>
        </SheetContent>
      </Sheet>

      {submitError && (
        <p className="text-xs text-destructive px-1">{submitError}</p>
      )}
    </div>
  )
}
