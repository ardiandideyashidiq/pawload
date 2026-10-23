import { useCallback, useEffect, useMemo, useState } from 'react'
import type { TransferRecord } from '@/types/transfer'
import {
  cancelTransfer,
  fetchTransfers,
  openTransfer,
  pauseTransfer,
  resumeTransfer,
} from '@/lib/api'

export function useTransfers() {
  const [transfers, setTransfers] = useState<TransferRecord[]>([])
  const [connected, setConnected] = useState(false)

  const reload = useCallback(async () => {
    try {
      const data = await fetchTransfers()
      setTransfers(data)
    } catch (err) {
      console.error('Failed to load transfers', err)
    }
  }, [])

  useEffect(() => {
    reload()

    const es = new EventSource('/api/events')
    es.onopen = () => {
      setConnected(true)
      reload()
    }
    es.onerror = () => setConnected(false)
      es.addEventListener('init', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as TransferRecord[]
          if (Array.isArray(data)) setTransfers(data)
        } catch (err) {
          console.error('Failed to parse init event', err)
        }
      })

      const handleTransferEvent = (e: MessageEvent) => {
        try {
          const parsed = JSON.parse(e.data)
          const item: TransferRecord =
            parsed && parsed.data && parsed.data.id
              ? (parsed.data as TransferRecord)
              : (parsed as TransferRecord)
          if (!item || !item.id) return

          setTransfers((prev) => {
            const index = prev.findIndex((t) => t.id === item.id)
            if (index >= 0) {
              const next = [...prev]
              next[index] = { ...next[index], ...item }
              return next
            }
            return [item, ...prev]
          })
        } catch (err) {
          console.error('Failed to parse transfer event', err)
        }
      }

      es.onmessage = handleTransferEvent
      es.addEventListener('transfer_added', handleTransferEvent)
      es.addEventListener('transfer_progress', handleTransferEvent)
      es.addEventListener('transfer_completed', handleTransferEvent)
      es.addEventListener('transfer_paused', handleTransferEvent)
      es.addEventListener('transfer_resumed', handleTransferEvent)
      es.addEventListener('transfer_cancelled', handleTransferEvent)
      es.addEventListener('transfer_error', handleTransferEvent)
    return () => {
      es.close()
    }
  }, [reload])

  const activeTransfers = useMemo(
    () =>
      transfers.filter(
        (t) => t.status === 'running' || t.status === 'queued' || t.status === 'paused'
      ),
    [transfers]
  )

  const completedTransfers = useMemo(
    () =>
      transfers.filter(
        (t) => t.status === 'completed' || t.status === 'cancelled' || t.status === 'error'
      ),
    [transfers]
  )

  const totalDownloadSpeed = useMemo(
    () =>
      activeTransfers
        .filter((t) => t.type === 'download' && t.status === 'running')
        .reduce((acc, t) => acc + (t.speed_bps || 0), 0),
    [activeTransfers]
  )

  const totalUploadSpeed = useMemo(
    () =>
      activeTransfers
        .filter((t) => t.type === 'upload' && t.status === 'running')
        .reduce((acc, t) => acc + (t.speed_bps || 0), 0),
    [activeTransfers]
  )

  const handlePause = useCallback(async (id: string) => {
    try {
      await pauseTransfer(id)
    } catch (err) {
      console.error(err)
    }
  }, [])

  const handleResume = useCallback(async (id: string) => {
    try {
      await resumeTransfer(id)
    } catch (err) {
      console.error(err)
    }
  }, [])

  const handleCancel = useCallback(async (id: string) => {
    try {
      await cancelTransfer(id)
    } catch (err) {
      console.error(err)
    }
  }, [])

  const handleOpen = useCallback(async (id: string) => {
    try {
      await openTransfer(id)
    } catch (err) {
      console.error(err)
    }
  }, [])

  const clearCompleted = useCallback(() => {
    setTransfers((prev) =>
      prev.filter(
        (t) => t.status === 'running' || t.status === 'queued' || t.status === 'paused'
      )
    )
  }, [])

  return {
    clearCompleted,
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
  }
}
