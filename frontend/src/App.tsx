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
import { ArrowUp, HardHat, Moon, Package, RotateCcw, Sun, Wrench } from 'lucide-react'

import { BenchmarkPage } from '@/benchmark/BenchmarkPage'
import { Avatar } from '@/components/Avatar'
import { MessageBubble, type Message } from '@/components/MessageBubble'
import { PendingCard } from '@/components/PendingCard'
import { WorkspacePanel } from '@/components/WorkspacePanel'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { useTheme } from '@/lib/theme'
import { applyEvents, EMPTY_WORKSPACE, type Workspace } from '@/lib/workspace'

const SUGGESTIONS = [
  {
    icon: Wrench,
    title: 'Start a brake inspection',
    text: "I'm starting the brake pad inspection on bogie B2 of RV200-014.",
  },
  { icon: Package, title: 'Check spare parts', text: 'How many brake pads are in stock?' },
  {
    icon: HardHat,
    title: 'Safety before you start',
    text: 'What do I need to wear before working under the train?',
  },
]

let nextId = 1

type View = 'assistant' | 'benchmark'

// The view lives in the URL hash, so the benchmark page has a link of its own.
function currentView(): View {
  return window.location.hash === '#benchmark' ? 'benchmark' : 'assistant'
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<PendingAction[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState<Workspace>(EMPTY_WORKSPACE)
  const [view, setView] = useState<View>(currentView)
  const [theme, toggleTheme] = useTheme()
  const endRef = useRef<HTMLDivElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const onHashChange = () => setView(currentView())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

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
      <header className="flex items-center justify-between border-b bg-chrome px-4 py-3 text-chrome-foreground sm:px-6">
        <div className="flex items-center gap-3">
          <Avatar className="size-9" />
          <div>
            <h1 className="font-display text-lg leading-none font-semibold tracking-tight">MAIA</h1>
            <p className="mt-1 text-xs text-chrome-foreground/70">
              Maintenance assistant for the RV-200 demo depot
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-4">
          <nav aria-label="Pages" className="flex rounded-lg bg-white/10 p-1 text-sm">
            {(
              [
                ['assistant', 'Assistant', '#'],
                ['benchmark', 'Benchmark', '#benchmark'],
              ] as const
            ).map(([id, label, href]) => (
              <a
                key={id}
                href={href}
                aria-current={view === id ? 'page' : undefined}
                className={cn(
                  'rounded-md px-3 py-1 font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-hivis',
                  view === id
                    ? 'bg-hivis text-hivis-foreground'
                    : 'text-chrome-foreground/80 hover:text-chrome-foreground',
                )}
              >
                {label}
              </a>
            ))}
          </nav>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to night shift mode'}
            title={theme === 'dark' ? 'Light mode' : 'Night shift mode'}
            className="text-chrome-foreground hover:bg-white/10 hover:text-chrome-foreground"
          >
            {theme === 'dark' ? <Sun aria-hidden /> : <Moon aria-hidden />}
          </Button>
          {view === 'assistant' && (
            <Button
              variant="outline"
              size="sm"
              onClick={reset}
              disabled={busy}
              className="border-white/25 bg-white/5 text-chrome-foreground hover:bg-white/15 hover:text-chrome-foreground dark:bg-white/5"
            >
              <RotateCcw aria-hidden />
              Reset demo
            </Button>
          )}
        </div>
      </header>

      {view === 'benchmark' ? (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <BenchmarkPage />
        </main>
      ) : (
        <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="flex min-h-0 flex-col">
            <main className="flex-1 overflow-y-auto" aria-live="polite">
              <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
                {messages.length === 0 && (
                  <div className="pt-10">
                    <h2 className="max-w-xl font-display text-3xl leading-tight font-semibold tracking-tight text-primary sm:text-4xl">
                      What are you working on today?
                    </h2>
                    <p className="mt-3 max-w-lg text-[15px] text-muted-foreground">
                      MAIA walks you through RV-200 procedures one step at a time, straight from the
                      manual, and asks before it changes anything.
                    </p>
                    <div className="mt-8 grid gap-3 sm:grid-cols-3">
                      {SUGGESTIONS.map(({ icon: Icon, title, text }) => (
                        <button
                          key={title}
                          type="button"
                          disabled={!sessionId || busy}
                          onClick={() => send(text)}
                          className="flex flex-col items-start gap-3 rounded-2xl border bg-card p-4 text-left shadow-sm transition-colors outline-none hover:border-primary/40 focus-visible:ring-[3px] focus-visible:ring-ring/60 disabled:opacity-50"
                        >
                          <span className="flex size-9 items-center justify-center rounded-lg bg-secondary text-primary">
                            <Icon className="size-5" aria-hidden />
                          </span>
                          <span>
                            <span className="block text-sm font-semibold text-ink">{title}</span>
                            <span className="mt-1 block text-sm text-muted-foreground">{text}</span>
                          </span>
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
                  <div className="flex items-center gap-3">
                    <Avatar />
                    <span className="flex items-center gap-1" aria-label="MAIA is working">
                      {[0, 150, 300].map((delay) => (
                        <span
                          key={delay}
                          className="size-2 rounded-full bg-primary/60 motion-safe:animate-bounce"
                          style={{ animationDelay: `${delay}ms` }}
                        />
                      ))}
                    </span>
                  </div>
                )}
                {error && (
                  <p
                    role="alert"
                    className="rounded-xl border border-destructive/30 bg-card px-4 py-3 text-sm text-destructive"
                  >
                    {error}
                  </p>
                )}
                <div ref={endRef} />
              </div>
            </main>

            <form onSubmit={onSubmit} className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
              <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-md focus-within:border-hivis focus-within:ring-[3px] focus-within:ring-hivis/30">
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
                  className="max-h-40 min-h-10 resize-none border-0 bg-transparent text-[15px] shadow-none focus-visible:ring-0 md:text-[15px] dark:bg-transparent"
                />
                <Button
                  type="submit"
                  size="icon"
                  aria-label="Send"
                  className="size-10 shrink-0 rounded-xl"
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
      )}
    </div>
  )
}
