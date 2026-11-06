import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import {
  ApiError,
  confirmPending,
  createSession,
  resetDemo,
  sendMessage,
  type ChatReply,
  type PendingAction,
} from './api'
import { MessageBubble, type Message } from './components/MessageBubble'
import { PendingCard } from './components/PendingCard'
import './App.css'

const SUGGESTIONS = [
  "I'm starting the brake pad inspection on bogie B2 of RV200-014.",
  'How many brake pads are in stock?',
  'What do I need to wear before working under the train?',
]

let nextId = 1

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<PendingAction[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const started = useRef(false)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, pending])

  function add(message: Omit<Message, 'id'>) {
    setMessages((current) => [...current, { ...message, id: nextId++ }])
  }

  function showReply(reply: ChatReply) {
    add({ role: 'assistant', text: reply.text, events: reply.events })
    setPending(reply.pending)
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the MAIA server.')
    } finally {
      setBusy(false)
    }
  }

  function startSession() {
    run(async () => {
      setSessionId(await createSession())
    })
  }

  function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || !sessionId || busy) return
    add({ role: 'user', text: trimmed })
    setInput('')
    run(async () => showReply(await sendMessage(sessionId, trimmed)))
  }

  function answer(approved: boolean) {
    if (!sessionId) return
    add({ role: 'notice', text: approved ? 'You confirmed.' : 'You cancelled.' })
    run(async () => showReply(await confirmPending(sessionId, approved)))
  }

  function reset() {
    run(async () => {
      await resetDemo()
      setMessages([])
      setPending([])
      setSessionId(await createSession())
    })
  }

  useEffect(() => {
    // React runs effects twice in development; only start one session.
    if (started.current) return
    started.current = true
    startSession()
  }, [])

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    send(input)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send(input)
    }
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>MAIA</h1>
          <p className="subtitle">Maintenance assistant · RV-200 demo depot (fictional data)</p>
        </div>
        <button type="button" onClick={reset} disabled={busy}>
          Reset demo
        </button>
      </header>

      <main className="conversation" aria-live="polite">
        {messages.length === 0 && (
          <div className="welcome">
            <p>Tell MAIA what you are working on. Try:</p>
            <div className="suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={!sessionId || busy}
                  onClick={() => send(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {pending.length > 0 && <PendingCard actions={pending} busy={busy} onAnswer={answer} />}
        {busy && <p className="thinking">MAIA is working…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div ref={endRef} />
      </main>

      <form className="composer" onSubmit={onSubmit}>
        <label htmlFor="message" className="visually-hidden">
          Message
        </label>
        <textarea
          id="message"
          rows={2}
          maxLength={2000}
          placeholder={pending.length > 0 ? 'Or reply instead of confirming…' : 'Message MAIA…'}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={!sessionId}
        />
        <button type="submit" className="primary" disabled={!input.trim() || !sessionId || busy}>
          Send
        </button>
      </form>
    </div>
  )
}
