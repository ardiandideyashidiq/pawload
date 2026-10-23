import { useState } from 'react'
import { ArrowDownToLine, ArrowUpToLine, FolderOpen, Loader2, Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { inspectTarget, startDownload, startUpload } from '@/lib/api'
import type { InspectResult } from '@/types/transfer'

interface TransferHubProps {
  onTransferStarted: () => void
}

function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return 'Unknown size'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

function getProviderBadgeVariant(provider: string): 'sourceforge' | 'gofile' | 'vikingfile' | 'pixeldrain' | 'default' {
  const p = provider.toLowerCase()
  if (p === 'sourceforge' || p === 'gofile' || p === 'vikingfile' || p === 'pixeldrain') {
    return p
  }
  return 'default'
}

export function TransferHub({ onTransferStarted }: TransferHubProps) {
  const [mode, setMode] = useState<'download' | 'upload'>('download')
  const [target, setTarget] = useState('')
  const [concurrency, setConcurrency] = useState(8)
  const [mirror, setMirror] = useState<string>('auto')
  const [inspecting, setInspecting] = useState(false)
  const [starting, setStarting] = useState(false)
  const [inspectData, setInspectData] = useState<InspectResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Upload states
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadProvider, setUploadProvider] = useState<string>('gofile')
  const [remotePath, setRemotePath] = useState<string>('')
  const [isDragging, setIsDragging] = useState(false)
  const handleInspect = async () => {
    if (!target.trim()) return
    setInspecting(true)
    setError(null)
    setInspectData(null)
    try {
      const res = await inspectTarget(target.trim())
      setInspectData(res)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Inspection failed')
    } finally {
      setInspecting(false)
    }
  }

  const handleStartDownload = async () => {
    if (!target.trim()) return
    setStarting(true)
    setError(null)
    try {
      await startDownload({
        target: target.trim(),
        concurrency,
        mirror: mirror !== 'auto' ? mirror : undefined,
      })
      setTarget('')
      setInspectData(null)
      onTransferStarted()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start download')
    } finally {
      setStarting(false)
    }
  }

  const handleStartUpload = async () => {
    if (!uploadFile) return
    setStarting(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', uploadFile)
      fd.append('provider', uploadProvider)
      if (remotePath.trim()) fd.append('remote_path', remotePath.trim())

      await startUpload(fd)
      setUploadFile(null)
      setRemotePath('')
      onTransferStarted()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start upload')
    } finally {
      setStarting(false)
    }
  }

  return (
    <Card className="border-border bg-card/60 backdrop-blur-sm shadow-md">
      <CardContent className="p-4 space-y-4">
        {/* Mode Toggle */}
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex space-x-2">
            <Button
              variant={mode === 'download' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setMode('download')}
              className="space-x-1.5"
            >
              <ArrowDownToLine className="w-3.5 h-3.5" />
              <span>Download</span>
            </Button>
            <Button
              variant={mode === 'upload' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setMode('upload')}
              className="space-x-1.5"
            >
              <ArrowUpToLine className="w-3.5 h-3.5" />
              <span>Upload</span>
            </Button>
          </div>
          <div className="text-xs text-muted-foreground font-mono">
            SourceForge • GoFile • VikingFile • PixelDrain
          </div>
        </div>

        {error && (
          <div className="p-2.5 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs">
            {error}
          </div>
        )}

        {mode === 'download' ? (
          <div className="space-y-3">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  placeholder="Paste URL or target (e.g. https://gofile.io/d/... or sf:project/file.zip)"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleInspect()
                  }}
                  className="pr-20 font-mono text-xs"
                />
                {inspectData && (
                  <div className="absolute right-2 top-2">
                    <Badge variant={inspectData.provider.toLowerCase() as any}>
                      {inspectData.provider}
                    </Badge>
                  </div>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleInspect}
                disabled={inspecting || !target.trim()}
              >
                {inspecting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Search className="w-3.5 h-3.5 mr-1.5" />
                    Inspect
                  </>
                )}
              </Button>
              <Button
                size="sm"
                onClick={handleStartDownload}
                disabled={starting || !target.trim()}
              >
                {starting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <ArrowDownToLine className="w-3.5 h-3.5 mr-1.5" />
                    Download
                  </>
                )}
              </Button>
            </div>

            {/* Target Inspection Details Card */}
            {inspectData && (
              <div className="p-3 rounded-lg border border-border/80 bg-background/50 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Badge variant={getProviderBadgeVariant(inspectData.provider)}>
                      {inspectData.provider}
                    </Badge>
                    <span className="font-semibold text-foreground truncate max-w-xs">{inspectData.name}</span>
                  </div>
                  <div className="text-muted-foreground font-mono">
                    {formatBytes(inspectData.size)}
                  </div>
                </div>
                {inspectData.items && inspectData.items.length > 0 && (
                  <div className="text-[11px] text-muted-foreground">
                    Contains {inspectData.items.length} files
                  </div>
                )}
              </div>
            )}

            {/* Options Strip */}
            <div className="flex flex-wrap items-center gap-4 pt-1 text-xs text-muted-foreground">
              <div className="flex items-center space-x-2">
                <span>Concurrency:</span>
                <Select
                  value={concurrency.toString()}
                  onValueChange={(v) => setConcurrency(parseInt(v, 10))}
                >
                  <SelectTrigger className="w-20 h-7 text-xs font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1</SelectItem>
                    <SelectItem value="2">2</SelectItem>
                    <SelectItem value="4">4</SelectItem>
                    <SelectItem value="8">8</SelectItem>
                    <SelectItem value="16">16</SelectItem>
                    <SelectItem value="32">32</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {inspectData?.mirrors && inspectData.mirrors.length > 0 && (
                <div className="flex items-center space-x-2">
                  <span>Mirror:</span>
                  <Select value={mirror} onValueChange={setMirror}>
                    <SelectTrigger className="w-28 h-7 text-xs font-mono">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto</SelectItem>
                      {inspectData.mirrors.map((m) => (
                        <SelectItem key={m} value={m}>
                          {m}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Upload Mode */
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setIsDragging(false)
                  if (e.dataTransfer.files?.[0]) setUploadFile(e.dataTransfer.files[0])
                }}
                className={`relative border rounded-md p-2 bg-background/50 flex items-center justify-between transition-colors ${
                  isDragging ? 'border-primary ring-1 ring-primary bg-primary/5' : 'border-input'
                }`}
              >
                <span className="text-xs truncate max-w-[180px] font-mono">
                  {uploadFile ? uploadFile.name : 'Choose or drop local file...'}
                </span>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) setUploadFile(e.target.files[0])
                    }}
                  />
                  <Button variant="secondary" size="sm" type="button" className="pointer-events-none">
                    <FolderOpen className="w-3.5 h-3.5 mr-1" />
                    Browse
                  </Button>
                </label>
              </div>

              <div>
                <Select value={uploadProvider} onValueChange={setUploadProvider}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Destination Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gofile">GoFile</SelectItem>
                    <SelectItem value="sourceforge">SourceForge (SFTP)</SelectItem>
                    <SelectItem value="pixeldrain">PixelDrain</SelectItem>
                    <SelectItem value="vikingfile">VikingFile</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex gap-2">
                <Input
                  placeholder={
                    uploadProvider === 'sourceforge'
                      ? 'Remote folder (e.g. release)'
                      : uploadProvider === 'gofile'
                        ? 'Folder ID (optional)'
                        : 'Subfolder path (optional)'
                  }
                  value={remotePath}
                  onChange={(e) => setRemotePath(e.target.value)}
                  className="font-mono text-xs"
                />
                <Button
                  size="sm"
                  onClick={handleStartUpload}
                  disabled={starting || !uploadFile}
                >
                  {starting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <ArrowUpToLine className="w-3.5 h-3.5 mr-1" />
                      Upload
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
