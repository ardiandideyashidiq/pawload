import { useState } from 'react'
import { Download, Inbox } from 'lucide-react'
import { Sidebar } from '@/components/layout/Sidebar'
import { StatusBar } from '@/components/layout/StatusBar'
import { TransferHub } from '@/components/hub/TransferHub'
import { ActiveCard } from '@/components/queue/ActiveCard'
import { CompletedCard } from '@/components/queue/CompletedCard'
import { SettingsModal } from '@/components/settings/SettingsModal'
import { useConfig } from '@/hooks/use-config'
import { useTransfers } from '@/hooks/use-transfers'

export default function App() {
  const [tab, setTab] = useState<'transfers' | 'completed'>('transfers')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { config } = useConfig()
  const {
    activeTransfers,
    completedTransfers,
    connected,
    totalDownloadSpeed,
    totalUploadSpeed,
    reload,
    handlePause,
    handleResume,
    handleCancel,
    handleOpen,
  } = useTransfers()

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground select-none">
      {/* Sidebar */}
      <Sidebar
        activeCount={activeTransfers.length}
        completedCount={completedTransfers.length}
        connected={connected}
        totalDownloadSpeed={totalDownloadSpeed}
        totalUploadSpeed={totalUploadSpeed}
        currentTab={tab}
        onSelectTab={setTab}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header / Omnibar Hub */}
        <div className="p-4 border-b border-border bg-card/20 shrink-0">
          <TransferHub onTransferStarted={reload} />
        </div>

        {/* Content Body */}
        <main className="flex-1 overflow-y-auto p-4 space-y-3">
          {tab === 'transfers' ? (
            activeTransfers.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                    Active Queue ({activeTransfers.length})
                  </h3>
                </div>
                {activeTransfers.map((item) => (
                  <ActiveCard
                    key={item.id}
                    transfer={item}
                    onPause={handlePause}
                    onResume={handleResume}
                    onCancel={handleCancel}
                  />
                ))}
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-muted-foreground space-y-2 border border-dashed border-border/60 rounded-xl">
                <Inbox className="w-8 h-8 stroke-1 text-muted-foreground/60" />
                <p className="text-xs">No active transfers running</p>
                <p className="text-[11px] text-muted-foreground/50">
                  Paste a URL or project in the box above to start downloading
                </p>
              </div>
            )
          ) : completedTransfers.length > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                  Finished History ({completedTransfers.length})
                </h3>
              </div>
              {completedTransfers.map((item) => (
                <CompletedCard key={item.id} transfer={item} onOpen={handleOpen} />
              ))}
            </div>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-muted-foreground space-y-2 border border-dashed border-border/60 rounded-xl">
              <Download className="w-8 h-8 stroke-1 text-muted-foreground/60" />
              <p className="text-xs">No completed transfers yet</p>
            </div>
          )}
        </main>

        {/* Bottom Status Bar */}
        <StatusBar
          activeCount={activeTransfers.length}
          connected={connected}
          configPath={config.config_path}
        />
      </div>

      {/* Settings Modal */}
      <SettingsModal open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  )
}
