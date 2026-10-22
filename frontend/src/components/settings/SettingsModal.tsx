import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
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

  useEffect(() => {
    if (open) {
      setFormData(config)
      setSuccess(false)
    }
  }, [open, config])

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
            Configuration stored at unified <code className="font-mono text-xs">{config.config_path || '~/.config/sourceforge/config.toml'}</code>
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
                  value={formData.global?.default_concurrency || 8}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      global: {
                        ...prev.global,
                        default_concurrency: parseInt(e.target.value, 10) || 8,
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
                <label className="text-xs text-muted-foreground">Default Mirror</label>
                <Input
                  value={formData.sourceforge?.default_mirror || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      sourceforge: { ...prev.sourceforge, default_mirror: e.target.value },
                    }))
                  }
                  placeholder="e.g. master, autonumber"
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
                <label className="text-xs text-emerald-400">GoFile API Token</label>
                <Input
                  type="password"
                  value={formData.gofile?.api_token || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      gofile: { ...prev.gofile, api_token: e.target.value },
                    }))
                  }
                  placeholder="Token"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-purple-400">VikingFile API Key</label>
                <Input
                  type="password"
                  value={formData.vikingfile?.api_key || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      vikingfile: { ...prev.vikingfile, api_key: e.target.value },
                    }))
                  }
                  placeholder="Key"
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
            <h4 className="text-xs font-semibold uppercase tracking-wider text-sky-400">Telegram Bot Notifications</h4>
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
                  placeholder="e.g. -100123456789"
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
