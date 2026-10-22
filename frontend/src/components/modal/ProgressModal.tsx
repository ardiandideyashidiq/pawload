import {
  ArrowDownToLine,
  ArrowUpToLine,
  Clock,
  Cpu,
  FolderOpen,
  Gauge,
  Pause,
  Play,
  X,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import type { TransferRecord } from '@/types/transfer'

interface ProgressModalProps {
  transfer: TransferRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onPause: (id: string) => void
  onResume: (id: string) => void
  onCancel: (id: string) => void
  onOpenFolder: (id: string) => void
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

export function ProgressModal({
  transfer,
  open,
  onOpenChange,
  onPause,
  onResume,
  onCancel,
  onOpenFolder,
}: ProgressModalProps) {
  if (!transfer) return null

  const isRunning = transfer.status === 'running'
  const isPaused = transfer.status === 'paused'
  const isCompleted = transfer.status === 'completed'
  const isError = transfer.status === 'error'
  const isCancelled = transfer.status === 'cancelled'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto border-border bg-card shadow-2xl">
        <DialogHeader className="space-y-2">
          <div className="flex items-center space-x-2">
            <Badge variant={getProviderVariant(transfer.provider)}>
              {transfer.provider}
            </Badge>
            <Badge variant="outline" className="text-[10px] uppercase font-mono">
              {transfer.type === 'download' ? (
                <ArrowDownToLine className="w-3 h-3 mr-1 text-primary inline" />
              ) : (
                <ArrowUpToLine className="w-3 h-3 mr-1 text-emerald-400 inline" />
              )}
              {transfer.type}
            </Badge>
            <Badge
              variant={
                isCompleted
                  ? 'secondary'
                  : isError
                    ? 'destructive'
                    : isCancelled || isPaused
                      ? 'outline'
                      : 'default'
              }
              className="text-[10px] uppercase font-mono"
            >
              {transfer.status}
            </Badge>
          </div>
          <DialogTitle className="text-base font-semibold text-foreground truncate max-w-xl">
            {transfer.name}
          </DialogTitle>
          <DialogDescription className="font-mono text-xs text-muted-foreground truncate">
            {transfer.dest_path || transfer.target}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {/* Main Progress Bar & Percentage */}
          <div className="space-y-2 p-4 rounded-xl border border-border/80 bg-background/50">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="font-semibold text-foreground text-sm">
                {transfer.progress_percent.toFixed(1)}%
              </span>
              <span className="text-muted-foreground">
                {formatBytes(transfer.completed_bytes)} / {formatBytes(transfer.total_bytes)}
              </span>
            </div>

            <Progress
              value={transfer.progress_percent}
              className="h-4 bg-secondary border border-border/80"
              indicatorClassName={
                isRunning
                  ? 'striped-bar bg-primary shadow-sm'
                  : isPaused
                    ? 'bg-amber-500'
                    : isCompleted
                      ? 'bg-emerald-500'
                      : 'bg-primary'
              }
            />

            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground pt-1">
              <span>Status: <span className="font-medium uppercase text-foreground">{transfer.status}</span></span>
              {isRunning && (
                <span>ETA: <span className="text-foreground font-semibold">{formatEta(transfer.eta_seconds)}</span></span>
              )}
            </div>
          </div>

          {/* Real-time Metrics Grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 rounded-lg border border-border/60 bg-card/60 space-y-1">
              <div className="flex items-center space-x-1.5 text-xs text-muted-foreground font-mono">
                <Gauge className="w-3.5 h-3.5 text-primary" />
                <span>Transfer Speed</span>
              </div>
              <div className="text-base font-bold font-mono text-foreground">
                {isRunning ? formatSpeed(transfer.speed_bps) : '0 B/s'}
              </div>
            </div>

            <div className="p-3 rounded-lg border border-border/60 bg-card/60 space-y-1">
              <div className="flex items-center space-x-1.5 text-xs text-muted-foreground font-mono">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span>Time Remaining</span>
              </div>
              <div className="text-base font-bold font-mono text-foreground">
                {isRunning ? formatEta(transfer.eta_seconds) : isCompleted ? 'Finished' : '--'}
              </div>
            </div>

            <div className="p-3 rounded-lg border border-border/60 bg-card/60 space-y-1">
              <div className="flex items-center space-x-1.5 text-xs text-muted-foreground font-mono">
                <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                <span>Workers</span>
              </div>
              <div className="text-base font-bold font-mono text-foreground">
                {transfer.concurrency} parallel
              </div>
            </div>
          </div>

          {/* Parallel Worker Concurrency Visualizer */}
          {transfer.concurrency > 1 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                Active Concurrency Pipeline ({transfer.concurrency} Slots)
              </h4>
              <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
                {Array.from({ length: transfer.concurrency }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-8 rounded-md border flex items-center justify-center font-mono text-[10px] transition-colors ${
                      isRunning
                        ? 'border-primary/40 bg-primary/10 text-primary animate-pulse'
                        : isCompleted
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                          : 'border-border/60 bg-secondary/30 text-muted-foreground'
                    }`}
                  >
                    Slot {i + 1}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Message Box */}
          {isError && transfer.error && (
            <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive space-y-1 text-xs">
              <div className="flex items-center space-x-2 font-semibold">
                <XCircle className="w-4 h-4 shrink-0" />
                <span>Transfer Failed</span>
              </div>
              <p className="font-mono text-[11px] break-all">{transfer.error}</p>
            </div>
          )}

          {/* Details Table */}
          <div className="space-y-2 border-t border-border pt-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground font-mono">
              Transfer Information
            </h4>
            <div className="rounded-lg border border-border/60 bg-background/40 divide-y divide-border/60 text-xs font-mono">
              <div className="p-2.5 flex justify-between gap-4">
                <span className="text-muted-foreground shrink-0">Source Target</span>
                <span className="text-foreground truncate select-all">{transfer.target}</span>
              </div>
              {transfer.dest_path && (
                <div className="p-2.5 flex justify-between gap-4">
                  <span className="text-muted-foreground shrink-0">Local Destination</span>
                  <span className="text-foreground truncate select-all">{transfer.dest_path}</span>
                </div>
              )}
              {transfer.mirror && (
                <div className="p-2.5 flex justify-between gap-4">
                  <span className="text-muted-foreground shrink-0">Selected Mirror</span>
                  <span className="text-foreground">{transfer.mirror}</span>
                </div>
              )}
              <div className="p-2.5 flex justify-between gap-4">
                <span className="text-muted-foreground shrink-0">Transfer ID</span>
                <span className="text-muted-foreground select-all">{transfer.id}</span>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter className="flex flex-row items-center justify-between gap-2 pt-2 border-t border-border">
          <div className="flex items-center space-x-2">
            {isRunning && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPause(transfer.id)}
                className="space-x-1.5 text-xs"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </Button>
            )}
            {isPaused && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onResume(transfer.id)}
                className="space-x-1.5 text-xs text-emerald-400 hover:text-emerald-300"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Resume</span>
              </Button>
            )}
            {(isRunning || isPaused) && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  onCancel(transfer.id)
                  onOpenChange(false)
                }}
                className="space-x-1.5 text-xs"
              >
                <X className="w-3.5 h-3.5" />
                <span>Cancel</span>
              </Button>
            )}
            {isCompleted && transfer.dest_path && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onOpenFolder(transfer.id)}
                className="space-x-1.5 text-xs"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>Open Folder</span>
              </Button>
            )}
          </div>

          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} className="text-xs">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
