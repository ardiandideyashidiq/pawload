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
  path?: string
  config_path?: string
  global?: {
    concurrency?: number
    download_dir?: string
    chunk_size?: number
    user_agent?: string
    timeout?: number
  }
  sourceforge?: {
    username?: string
    project?: string
    key_path?: string
    default_mirror?: string
    concurrency?: number
    chunk_size?: number
  }
  gofile?: {
    token?: string
    account_id?: string
    root_folder?: string
    concurrency?: number
    chunk_size?: number
  }
  vikingfile?: {
    user?: string
    concurrency?: number
    chunk_size?: number
  }
  pixeldrain?: {
    api_key?: string
    concurrency?: number
    chunk_size?: number
  }
  telegram?: {
    bot_token?: string
    chat_id?: string
    thread_id?: number
    throttle_interval?: number
    parse_mode?: string
  }
}
