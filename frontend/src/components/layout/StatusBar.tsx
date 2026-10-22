interface StatusBarProps {
  activeCount: number
  connected: boolean
  configPath?: string
}

export function StatusBar({ activeCount, connected, configPath }: StatusBarProps) {
  return (
    <footer className="h-7 border-t border-border bg-card/70 px-4 flex items-center justify-between text-[11px] font-mono text-muted-foreground select-none shrink-0">
      <div className="flex items-center space-x-4">
        <span className="flex items-center space-x-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-emerald-500 animate-pulse' : 'bg-destructive'
            }`}
          />
          <span>{connected ? 'Backend Online' : 'Connecting to daemon...'}</span>
        </span>
        <span>•</span>
        <span>Active Jobs: {activeCount}</span>
      </div>

      <div className="truncate max-w-sm" title={configPath || 'config.toml'}>
        Config: {configPath || '~/.config/sourceforge/config.toml'}
      </div>
    </footer>
  )
}
