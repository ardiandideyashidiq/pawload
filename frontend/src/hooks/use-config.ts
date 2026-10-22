import { useCallback, useEffect, useState } from 'react'
import type { ConfigData } from '@/types/transfer'
import { fetchConfig, saveConfig } from '@/lib/api'

export function useConfig() {
  const [config, setConfig] = useState<ConfigData>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchConfig()
      setConfig(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const update = useCallback(
    async (updated: Partial<ConfigData>) => {
      setSaving(true)
      setError(null)
      try {
        await saveConfig(updated)
        await reload()
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to save configuration')
        throw err
      } finally {
        setSaving(false)
      }
    },
    [reload]
  )

  return {
    config,
    loading,
    saving,
    error,
    reload,
    update,
  }
}
