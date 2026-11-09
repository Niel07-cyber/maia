// Typed client for the MAIA backend API.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type ToolEvent = {
  name: string
  ok: boolean
  confirmed: boolean | null
  // What the tool returned (JSON). Its shape depends on the tool; see the types below.
  result?: unknown
}

export type Band = 'within_limits' | 'below_warning' | 'below_minimum' | 'at_or_below_critical'

export type Priority = 'low' | 'medium' | 'high'

export type Assessment = {
  reading: number
  unit: string
  band: Band
  limits: string
  withdraw_from_service: boolean
  work_order_priority: Priority | null
}

export type AssetInfo = {
  asset_id: string
  vehicle_id: string
  vehicle_status: 'in_service' | 'out_of_service'
  name: string
  open_work_orders: number
}

export type StepLogged = {
  step_log_id: number
  procedure_code: string
  step: number
  reading: number | null
  unit: string | null
  assessment: Assessment | null
}

export type WorkOrderInfo = {
  work_order_id: number
  asset_id: string | null
  vehicle_id: string
  procedure_code: string
  priority: Priority
  description: string
}

export type ReservationInfo = {
  work_order_id: number
  part_number: string
  quantity: number
}

export type PendingAction = {
  tool: string
  description: string
}

export type ChatReply = {
  text: string
  events: ToolEvent[]
  pending: PendingAction[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return parse<T>(response)
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response
      .json()
      .then((data: { detail?: unknown }) => data.detail)
      .catch(() => undefined)
    throw new ApiError(
      response.status,
      typeof detail === 'string' ? detail : `Request failed (${response.status})`,
    )
  }
  return (await response.json()) as T
}

export async function createSession(): Promise<string> {
  const data = await post<{ session_id: string }>('/api/sessions')
  return data.session_id
}

export function sendMessage(sessionId: string, text: string): Promise<ChatReply> {
  return post<ChatReply>(`/api/sessions/${sessionId}/messages`, { text })
}

export function confirmPending(sessionId: string, approved: boolean): Promise<ChatReply> {
  return post<ChatReply>(`/api/sessions/${sessionId}/confirmation`, { approved })
}

export async function resetDemo(): Promise<void> {
  await post<{ status: string }>('/api/demo/reset')
}

/** Turn a push-to-talk recording into text. */
export async function transcribe(audio: Blob): Promise<string> {
  const form = new FormData()
  const extension = audio.type.includes('mp4') ? 'mp4' : audio.type.includes('ogg') ? 'ogg' : 'webm'
  form.append('audio', audio, `speech.${extension}`)
  // No Content-Type header: the browser sets the multipart boundary itself.
  const response = await fetch(`${API_URL}/api/transcribe`, { method: 'POST', body: form })
  const data = await parse<{ text: string }>(response)
  return data.text
}
