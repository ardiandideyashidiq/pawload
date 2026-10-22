import { CheckCircle2, FolderOpen, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { TransferRecord } from '@/types/transfer'

interface CompletedCardProps {
  transfer: TransferRecord
  onOpen: (id: string) => void
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

function getProviderVariant(provider: string): 'sourceforge' | 'gofile' | 'vikingfile' | 'pixeldrain' | 'default' {
  const p = provider.toLowerCase()
  if (p === 'sourceforge' || p === 'gofile' || p === 'vikingfile' || p === 'pixeldrain') {
    return p
  }
  return 'default'
}

export function CompletedCard({ transfer, onOpen }: CompletedCardProps) {
  const isSuccess = transfer.status === 'completed'
  const isError = transfer.status === 'error'
  const isCancelled = transfer.status === 'cancelled'

  return (
    <Card className="border-border bg-card/40 hover:bg-card/70 transition-colors">
      <CardContent className="p-3 flex items-center justify-between gap-3">
        <div className="flex items-center space-x-3 min-w-0">
          {isSuccess && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
          {isError && <XCircle className="w-4 h-4 text-destructive shrink-0" />}
          {isCancelled && <XCircle className="w-4 h-4 text-muted-foreground shrink-0" />}

          <div className="space-y-0.5 min-w-0">
            <div className="flex items-center space-x-2">
              <Badge variant={getProviderVariant(transfer.provider)}>
                {transfer.provider}
              </Badge>
              <span className="text-xs font-semibold text-foreground truncate max-w-sm" title={transfer.name}>
                {transfer.name}
              </span>
            </div>
            {isError && transfer.error ? (
              <p className="text-[11px] text-destructive truncate max-w-md">{transfer.error}</p>
            ) : (
              <p className="text-[11px] font-mono text-muted-foreground">
                {formatBytes(transfer.total_bytes || transfer.completed_bytes)} • {transfer.type}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          {isSuccess && transfer.dest_path && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onOpen(transfer.id)}
              className="h-7 text-xs"
            >
              <FolderOpen className="w-3.5 h-3.5 mr-1.5" />
              Open Folder
            </Button>
          )}
          <Badge
            variant={isSuccess ? 'secondary' : isError ? 'destructive' : 'outline'}
            className="text-[10px]"
          >
            {transfer.status}
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}
