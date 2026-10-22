export type TransferType = 'download' | 'upload'
export type TransferStatus = 'queued' | 'running' | 'paused' | 'completed' | 'cancelled' | 'error'

export interface TransferRecord {
  id: string
  type: TransferType
  provider: string
  name: string
  target: string
  dest_path?: string
  status: TransferStatus
  total_bytes: number
  completed_bytes: number
  speed_bps: number
  eta_seconds?: number | null
  progress_percent: number
  concurrency: number
  mirror?: string | null
  error?: string | null
  created_at: number
  updated_at: number
}

export interface InspectResult {
  provider: string
  name: string
  size?: number | null
  file_count?: number
  items?: Array<{ name: string; size?: number; type?: string }>
  mirrors?: string[]
}

export interface ConfigData {
  config_path?: string
  global?: {
    user_agent?: string
    timeout?: number
    default_concurrency?: number
    chunk_size?: number
    download_dir?: string
  }
  sourceforge?: {
    username?: string
    api_key?: string
    default_mirror?: string
  }
  gofile?: {
    api_token?: string
  }
  vikingfile?: {
    api_key?: string
  }
  pixeldrain?: {
    api_key?: string
  }
  telegram?: {
    bot_token?: string
    chat_id?: string
    progress_frequency?: number
  }
}
