import { Cloud, CheckCircle2, Download, Settings, Upload, Wifi, WifiOff } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface SidebarProps {
  activeCount: number
  completedCount: number
  connected: boolean
  totalDownloadSpeed: number
  totalUploadSpeed: number
  currentTab: 'transfers' | 'completed'
  onSelectTab: (tab: 'transfers' | 'completed') => void
  onOpenSettings: () => void
}

function formatSpeed(bps: number): string {
  if (bps <= 0) return '0 B/s'
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  let size = bps
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

export function Sidebar({
  activeCount,
  completedCount,
  connected,
  totalDownloadSpeed,
  totalUploadSpeed,
  currentTab,
  onSelectTab,
  onOpenSettings,
}: SidebarProps) {
  return (
    <aside className="w-64 border-r border-border bg-card/50 flex flex-col justify-between shrink-0 select-none">
      <div className="p-4 space-y-6">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-primary/10 border border-primary/20 text-primary relative">
            <Cloud className="w-5 h-5" />
            {connected && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-background" />
            )}
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-foreground">Pawload</h1>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono">Transfer Core</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="space-y-1">
          <button
            onClick={() => onSelectTab('transfers')}
            className={`w-full flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg transition-colors cursor-pointer ${
              currentTab === 'transfers'
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
            }`}
          >
            <div className="flex items-center space-x-2">
              <Download className="w-4 h-4" />
              <span>Transfers</span>
            </div>
            {activeCount > 0 && (
              <Badge variant="default" className="h-5 px-1.5 text-[10px] font-mono">
                {activeCount}
              </Badge>
            )}
          </button>

          <button
            onClick={() => onSelectTab('completed')}
            className={`w-full flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg transition-colors cursor-pointer ${
              currentTab === 'completed'
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
            }`}
          >
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Finished</span>
            </div>
            {completedCount > 0 && (
              <Badge variant="secondary" className="h-5 px-1.5 text-[10px] font-mono text-muted-foreground">
                {completedCount}
              </Badge>
            )}
          </button>
        </nav>
      </div>

      {/* Speed & Live Status Widget */}
      <div className="p-4 space-y-4 border-t border-border bg-background/20">
        <div className="space-y-2 font-mono text-[11px]">
          <div className="flex items-center justify-between text-muted-foreground bg-primary/5 px-2.5 py-1.5 rounded-md border border-primary/10">
            <div className="flex items-center space-x-1.5">
              <Download className="w-3.5 h-3.5 text-primary" />
              <span>Download</span>
            </div>
            <span className="text-foreground font-semibold font-mono">{formatSpeed(totalDownloadSpeed)}</span>
          </div>
          <div className="flex items-center justify-between text-muted-foreground bg-emerald-500/5 px-2.5 py-1.5 rounded-md border border-emerald-500/10">
            <div className="flex items-center space-x-1.5">
              <Upload className="w-3.5 h-3.5 text-emerald-400" />
              <span>Upload</span>
            </div>
            <span className="text-foreground font-semibold font-mono">{formatSpeed(totalUploadSpeed)}</span>
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between border-t border-border/50">
          <div className="flex items-center space-x-1.5 text-[11px]">
            {connected ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 font-medium">Live SSE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-destructive" />
                <span className="text-destructive font-medium">Disconnected</span>
              </>
            )}
          </div>
          <Button variant="ghost" size="icon" onClick={onOpenSettings} title="Settings">
            <Settings className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </Button>
        </div>
      </div>
    </aside>
  )
}
