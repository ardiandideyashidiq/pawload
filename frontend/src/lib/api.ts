import type { ConfigData, InspectResult, TransferRecord } from '@/types/transfer'

const BASE_URL = '/api'

export async function fetchTransfers(): Promise<TransferRecord[]> {
  const res = await fetch(`${BASE_URL}/transfers`)
  if (!res.ok) throw new Error(`Failed to load transfers: ${res.statusText}`)
  return res.json()
}

export async function inspectTarget(target: string): Promise<InspectResult> {
  const res = await fetch(`${BASE_URL}/inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Inspection failed')
  return data
}

export async function startDownload(payload: {
  target: string
  dest_dir?: string
  concurrency?: number
  mirror?: string
}): Promise<{ transfer_id: string; message: string }> {
  const res = await fetch(`${BASE_URL}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Download start failed')
  return data
}

export async function startUpload(
  formData: FormData
): Promise<{ transfer_id: string; message: string }> {
  const res = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Upload start failed')
  return data
}

export async function pauseTransfer(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/transfers/${id}/pause`, { method: 'POST' })
  if (!res.ok) throw new Error('Pause failed')
}

export async function resumeTransfer(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/transfers/${id}/resume`, { method: 'POST' })
  if (!res.ok) throw new Error('Resume failed')
}

export async function cancelTransfer(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/transfers/${id}/cancel`, { method: 'POST' })
  if (!res.ok) throw new Error('Cancel failed')
}

export async function openTransfer(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transfer_id: id }),
  })
  if (!res.ok) throw new Error('Failed to open file location')
}

export async function fetchConfig(): Promise<ConfigData> {
  const res = await fetch(`${BASE_URL}/config`)
  if (!res.ok) throw new Error('Failed to load configuration')
  return res.json()
}

export async function saveConfig(
  config: Partial<ConfigData>
): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Failed to save configuration')
  return data
}
