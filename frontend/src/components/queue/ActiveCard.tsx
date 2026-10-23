import { ArrowDownToLine, ArrowUpToLine, Maximize2, Pause, Play, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { TransferRecord } from '@/types/transfer'

interface ActiveCardProps {
  transfer: TransferRecord
  onPause: (id: string) => void
  onResume: (id: string) => void
  onCancel: (id: string) => void
  onSelect?: (transfer: TransferRecord) => void
}

function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

function formatSpeed(bps: number): string {
  if (bps <= 0) return '0 B/s'
  return `${formatBytes(bps)}/s`
}

function formatEta(seconds?: number | null): string {
  if (seconds === undefined || seconds === null || seconds <= 0 || !isFinite(seconds)) return '--'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  const remSeconds = Math.round(seconds % 60)
  if (minutes < 60) return `${minutes}m ${remSeconds}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

function getProviderVariant(
  provider: string
): 'sourceforge' | 'gofile' | 'vikingfile' | 'pixeldrain' | 'default' {
  const p = provider.toLowerCase()
  if (p === 'sourceforge' || p === 'gofile' || p === 'vikingfile' || p === 'pixeldrain') {
    return p
  }
  return 'default'
}

export function ActiveCard({ transfer, onPause, onResume, onCancel, onSelect }: ActiveCardProps) {
  const isRunning = transfer.status === 'running'
  const isPaused = transfer.status === 'paused'

  return (
    <Card className="border-border bg-card/80 hover:border-primary/50 transition-all shadow-sm">
      <CardContent className="p-4 space-y-3">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0 flex-1">
            <div className="flex items-center space-x-2">
              <Badge variant={getProviderVariant(transfer.provider)}>
                {transfer.provider}
              </Badge>
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                {transfer.type === 'download' ? (
                  <ArrowDownToLine className="w-3 h-3 text-primary" />
                ) : (
                  <ArrowUpToLine className="w-3 h-3 text-emerald-400" />
                )}
                {transfer.type}
              </span>
              {transfer.type === 'download' && transfer.concurrency && (
                <span className="text-[10px] font-mono text-muted-foreground">
                  • {transfer.concurrency} workers
                </span>
              )}
            </div>
            <h4
              onClick={() => onSelect?.(transfer)}
              className="text-sm font-semibold text-foreground truncate cursor-pointer hover:text-primary transition-colors"
              title={transfer.name}
            >
              {transfer.name}
            </h4>
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-1 shrink-0">
            {onSelect && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onSelect(transfer)}
                title="View progress modal & details"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
              >
                <Maximize2 className="w-4 h-4" />
              </Button>
            )}
            {isRunning && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onPause(transfer.id)}
                title="Pause transfer"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
              >
                <Pause className="w-4 h-4" />
              </Button>
            )}
            {isPaused && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onResume(transfer.id)}
                title="Resume transfer"
                className="h-8 w-8 text-emerald-400 hover:text-emerald-300"
              >
                <Play className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onCancel(transfer.id)}
              title="Cancel transfer"
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Progress bar container */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              {transfer.type === 'upload' && isRunning && transfer.progress_percent <= 0 ? (
                <>
                  <span className="text-emerald-400 font-medium">Streaming payload...</span>
                </>
              ) : (
                <span>{transfer.progress_percent.toFixed(1)}%</span>
              )}
            </span>
            <span className="text-muted-foreground">
              {formatBytes(transfer.completed_bytes)} / {formatBytes(transfer.total_bytes)}
            </span>
          </div>

          <Progress
            value={
              transfer.type === 'upload' && isRunning && transfer.progress_percent <= 0
                ? 100
                : transfer.progress_percent
            }
            className="h-3 bg-secondary/80 border border-border/80"
            indicatorClassName={
              isRunning
                ? transfer.type === 'upload' && transfer.progress_percent <= 0
                  ? 'striped-bar bg-emerald-500/80'
                  : 'striped-bar bg-primary shadow-sm'
                : isPaused
                  ? 'bg-amber-500'
                  : 'bg-primary'
            }
          />
        </div>
        {/* Footer info: speed, ETA, status */}
        <div className="flex items-center justify-between text-xs font-mono text-muted-foreground pt-0.5">
          <div className="flex items-center space-x-3">
            {isRunning && (
              <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                {formatSpeed(transfer.speed_bps)}
              </span>
            )}
            {isPaused && <span className="text-amber-400 font-semibold">PAUSED</span>}
            {transfer.status === 'queued' && <span className="text-muted-foreground">QUEUED</span>}
          </div>

          <div className="flex items-center space-x-2">
            {isRunning && <span>ETA: {formatEta(transfer.eta_seconds)}</span>}
            {transfer.error && (
              <span className="text-destructive truncate max-w-xs">{transfer.error}</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
