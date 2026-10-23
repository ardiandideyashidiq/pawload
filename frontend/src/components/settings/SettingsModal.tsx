import { useEffect, useState } from 'react'
import { Check, CheckCircle2, Loader2, Send, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useConfig } from '@/hooks/use-config'
import type { ConfigData } from '@/types/transfer'

interface SettingsModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  const { config, saving, update } = useConfig()
  const [formData, setFormData] = useState<ConfigData>({})
  const [success, setSuccess] = useState(false)
  const [testingTg, setTestingTg] = useState(false)
  const [tgResult, setTgResult] = useState<{ ok?: boolean; message?: string } | null>(null)
  useEffect(() => {
    if (open) {
      setFormData(config)
      setSuccess(false)
      setTgResult(null)
    }
  }, [open, config])

  const handleTestTelegram = async () => {
    setTestingTg(true)
    setTgResult(null)
    try {
      const res = await fetch('/api/telegram/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData.telegram || {}),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setTgResult({
          ok: true,
          message: `Connected as @${data.bot_username || 'bot'}. Sent test ping!`,
        })
      } else {
        setTgResult({
          ok: false,
          message: data.error || 'Connection failed',
        })
      }
    } catch (err: unknown) {
      setTgResult({
        ok: false,
        message: err instanceof Error ? err.message : 'Network error',
      })
    } finally {
      setTestingTg(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await update(formData)
      setSuccess(true)
      setTimeout(() => {
        setSuccess(false)
        onOpenChange(false)
      }, 1000)
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Transfer & Provider Settings</DialogTitle>
          <DialogDescription>
            Configuration stored at unified <code className="font-mono text-xs">{config.config_path || config.path || '~/.config/pawload/config.toml'}</code>
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSave} className="space-y-6 pt-2">
          {/* General Section */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">General</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Download Directory</label>
                <Input
                  value={formData.global?.download_dir || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      global: { ...prev.global, download_dir: e.target.value },
                    }))
                  }
                  placeholder="~/Downloads"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Default Concurrency</label>
                <Input
                  type="number"
                  min="1"
                  max="32"
                  value={formData.global?.concurrency || 4}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      global: {
                        ...prev.global,
                        concurrency: parseInt(e.target.value, 10) || 4,
                      },
                    }))
                  }
                  className="font-mono text-xs"
                />
              </div>
            </div>
          </div>

          {/* SourceForge Section */}
          <div className="space-y-3 border-t border-border pt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400">SourceForge</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Username</label>
                <Input
                  value={formData.sourceforge?.username || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      sourceforge: { ...prev.sourceforge, username: e.target.value },
                    }))
                  }
                  placeholder="Username"
                  className="text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Default Project</label>
                <Input
                  value={formData.sourceforge?.project || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      sourceforge: { ...prev.sourceforge, project: e.target.value },
                    }))
                  }
                  placeholder="e.g. my-project"
                  className="text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">SSH Key Path</label>
                <Input
                  value={formData.sourceforge?.key_path || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      sourceforge: { ...prev.sourceforge, key_path: e.target.value },
                    }))
                  }
                  placeholder="~/.ssh/id_ed25519"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Default Mirror</label>
                <Input
                  value={formData.sourceforge?.default_mirror || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      sourceforge: { ...prev.sourceforge, default_mirror: e.target.value },
                    }))
                  }
                  placeholder="e.g. master, autoselect"
                  className="font-mono text-xs"
                />
              </div>
            </div>
          </div>

          {/* API Keys Section */}
          <div className="space-y-3 border-t border-border pt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">API Credentials</h4>
            <div className="space-y-2">
              <div className="space-y-1">
                <label className="text-xs text-emerald-400">GoFile Account Token</label>
                <Input
                  type="password"
                  value={formData.gofile?.token || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      gofile: { ...prev.gofile, token: e.target.value },
                    }))
                  }
                  placeholder="Token (optional, auto-guest if omitted)"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-purple-400">VikingFile User Account Hash</label>
                <Input
                  value={formData.vikingfile?.user || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      vikingfile: { ...prev.vikingfile, user: e.target.value },
                    }))
                  }
                  placeholder="User Hash (optional)"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-cyan-400">PixelDrain API Key</label>
                <Input
                  type="password"
                  value={formData.pixeldrain?.api_key || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      pixeldrain: { ...prev.pixeldrain, api_key: e.target.value },
                    }))
                  }
                  placeholder="Key"
                  className="font-mono text-xs"
                />
              </div>
            </div>
          </div>

          {/* Telegram Notifications */}
          <div className="space-y-3 border-t border-border pt-4">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-sky-400">Telegram Bot Notifications</h4>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTestTelegram}
                disabled={testingTg || !formData.telegram?.bot_token}
                className="h-7 text-xs"
              >
                {testingTg ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                ) : (
                  <Send className="w-3.5 h-3.5 mr-1 text-sky-400" />
                )}
                Test Bot
              </Button>
            </div>

            {tgResult && (
              <div
                className={`p-2 rounded-md text-xs flex items-center space-x-1.5 ${
                  tgResult.ok
                    ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                    : 'bg-destructive/10 border border-destructive/20 text-destructive'
                }`}
              >
                {tgResult.ok ? (
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 shrink-0" />
                )}
                <span>{tgResult.message}</span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Bot Token</label>
                <Input
                  type="password"
                  value={formData.telegram?.bot_token || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      telegram: { ...prev.telegram, bot_token: e.target.value },
                    }))
                  }
                  placeholder="123456:ABC-DEF..."
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Chat ID</label>
                <Input
                  value={formData.telegram?.chat_id || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      telegram: { ...prev.telegram, chat_id: e.target.value },
                    }))
                  }
                  placeholder="e.g. 6665891737"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Topic Thread ID (Optional)</label>
                <Input
                  type="number"
                  value={formData.telegram?.thread_id || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      telegram: {
                        ...prev.telegram,
                        thread_id: e.target.value ? parseInt(e.target.value, 10) : undefined,
                      },
                    }))
                  }
                  placeholder="e.g. 1"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Throttle Interval (Seconds)</label>
                <Input
                  type="number"
                  step="0.5"
                  min="0.5"
                  value={formData.telegram?.throttle_interval || 2.0}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      telegram: {
                        ...prev.telegram,
                        throttle_interval: parseFloat(e.target.value) || 2.0,
                      },
                    }))
                  }
                  className="font-mono text-xs"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
              ) : success ? (
                <Check className="w-4 h-4 text-emerald-400 mr-1.5" />
              ) : null}
              {success ? 'Saved!' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
