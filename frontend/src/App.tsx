import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import {
  ApiError,
  confirmPending,
  createSession,
  resetDemo,
  sendMessage,
  type ChatReply,
  type PendingAction,
} from '@/api'
import { ArrowRight, ArrowUp, RotateCcw, TrainFront } from 'lucide-react'

import { MessageBubble, type Message } from '@/components/MessageBubble'
import { PendingCard } from '@/components/PendingCard'
import { WorkspacePanel } from '@/components/WorkspacePanel'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { applyEvents, EMPTY_WORKSPACE, type Workspace } from '@/lib/workspace'

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
  const [workspace, setWorkspace] = useState<Workspace>(EMPTY_WORKSPACE)
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
    setWorkspace((current) => applyEvents(current, reply.events))
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
      setWorkspace(EMPTY_WORKSPACE)
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
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <TrainFront className="size-5" aria-hidden />
          </div>
          <div>
            <h1 className="leading-tight font-semibold">MAIA</h1>
            <p className="text-xs text-muted-foreground">
              Maintenance assistant · RV-200 demo depot (fictional data)
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={reset} disabled={busy}>
          <RotateCcw aria-hidden />
          Reset demo
        </Button>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="flex min-h-0 flex-col">
          <main className="flex-1 overflow-y-auto" aria-live="polite">
            <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center pt-12 text-center">
                  <h2 className="text-2xl font-semibold tracking-tight">
                    What are you working on?
                  </h2>
                  <p className="mt-2 max-w-md text-sm text-muted-foreground">
                    MAIA guides you through RV-200 procedures step by step, from the manual, and
                    asks before changing anything.
                  </p>
                  <div className="mt-8 grid w-full gap-2">
                    {SUGGESTIONS.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        disabled={!sessionId || busy}
                        onClick={() => send(suggestion)}
                        className="group flex items-center justify-between rounded-xl border px-4 py-3 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50"
                      >
                        {suggestion}
                        <ArrowRight
                          className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                          aria-hidden
                        />
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {pending.length > 0 && (
                <PendingCard actions={pending} busy={busy} onAnswer={answer} />
              )}
              {busy && (
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <div className="flex size-7 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">
                    M
                  </div>
                  <span className="animate-pulse">MAIA is working…</span>
                </div>
              )}
              {error && (
                <p
                  role="alert"
                  className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive"
                >
                  {error}
                </p>
              )}
              <div ref={endRef} />
            </div>
          </main>

          <form onSubmit={onSubmit} className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
            <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm focus-within:ring-2 focus-within:ring-ring/40">
              <label htmlFor="message" className="sr-only">
                Message
              </label>
              <Textarea
                id="message"
                rows={1}
                maxLength={2000}
                placeholder={
                  pending.length > 0 ? 'Or reply instead of confirming…' : 'Message MAIA…'
                }
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onKeyDown}
                disabled={!sessionId}
                className="max-h-40 min-h-10 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
              />
              <Button
                type="submit"
                size="icon"
                aria-label="Send"
                className="shrink-0 rounded-xl"
                disabled={!input.trim() || !sessionId || busy}
              >
                <ArrowUp aria-hidden />
              </Button>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Demo with fictional data. Always follow your site's real procedures.
            </p>
          </form>
        </section>

        <WorkspacePanel workspace={workspace} className="hidden border-l lg:block" />
      </div>
    </div>
  )
}
