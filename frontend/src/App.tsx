import { useMemo, useState } from 'react'
import { CheckCircle2, Download, Inbox } from 'lucide-react'
import { Sidebar } from '@/components/layout/Sidebar'
import { StatusBar } from '@/components/layout/StatusBar'
import { TransferHub } from '@/components/hub/TransferHub'
import { ActiveCard } from '@/components/queue/ActiveCard'
import { CompletedCard } from '@/components/queue/CompletedCard'
import { ProgressModal } from '@/components/modal/ProgressModal'
import { SettingsModal } from '@/components/settings/SettingsModal'
import { useConfig } from '@/hooks/use-config'
import { useTransfers } from '@/hooks/use-transfers'
import type { TransferRecord } from '@/types/transfer'

export default function App() {
  const [tab, setTab] = useState<'transfers' | 'completed'>('transfers')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [selectedTransfer, setSelectedTransfer] = useState<TransferRecord | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const { config } = useConfig()
  const {
    transfers,
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

  const liveSelectedTransfer = useMemo(() => {
    if (!selectedTransfer) return null
    return transfers.find((t) => t.id === selectedTransfer.id) || selectedTransfer
  }, [selectedTransfer, transfers])

  const handleSelectTransfer = (item: TransferRecord) => {
    setSelectedTransfer(item)
    setModalOpen(true)
  }

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
        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Main View Segmented Header */}
          <div className="flex items-center justify-between border-b border-border/40 pb-2">
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setTab('transfers')}
                className={`flex items-center space-x-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  tab === 'transfers'
                    ? 'bg-secondary text-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-secondary/40 hover:text-foreground'
                }`}
              >
                <Download className="w-3.5 h-3.5" />
                <span>Active Queue</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-background/50 border border-border">
                  {activeTransfers.length}
                </span>
              </button>

              <button
                onClick={() => setTab('completed')}
                className={`flex items-center space-x-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  tab === 'completed'
                    ? 'bg-secondary text-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-secondary/40 hover:text-foreground'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Finished History</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-background/50 border border-border">
                  {completedTransfers.length}
                </span>
              </button>
            </div>
          </div>

          {/* Tab Content */}
          {tab === 'transfers' ? (
            activeTransfers.length > 0 ? (
              <div className="space-y-3">
                {activeTransfers.map((item) => (
                  <ActiveCard
                    key={item.id}
                    transfer={item}
                    onPause={handlePause}
                    onResume={handleResume}
                    onCancel={handleCancel}
                    onSelect={handleSelectTransfer}
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
              {completedTransfers.map((item) => (
                <CompletedCard
                  key={item.id}
                  transfer={item}
                  onOpen={handleOpen}
                  onSelect={handleSelectTransfer}
                />
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

      {/* Progress Detail Modal */}
      <ProgressModal
        transfer={liveSelectedTransfer}
        open={modalOpen}
        onOpenChange={setModalOpen}
        onPause={handlePause}
        onResume={handleResume}
        onCancel={handleCancel}
        onOpenFolder={handleOpen}
      />
    </div>
  )
}
