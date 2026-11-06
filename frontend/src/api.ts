// Typed client for the MAIA backend API.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type ToolEvent = {
  name: string
  ok: boolean
  confirmed: boolean | null
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
