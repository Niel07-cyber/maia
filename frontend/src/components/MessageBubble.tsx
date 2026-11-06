import Markdown from 'react-markdown'

import type { ToolEvent } from '@/api'
import { Avatar } from '@/components/Avatar'
import { cn } from '@/lib/utils'

export type Message = {
  id: number
  role: 'user' | 'assistant' | 'notice'
  text: string
  events?: ToolEvent[]
}

const TOOL_LABELS: Record<string, string> = {
  search_manual: 'Searched the manual',
  get_asset: 'Looked up the asset',
  check_stock: 'Checked stock',
  log_step: 'Logged a step',
  create_work_order: 'Work order',
  reserve_parts: 'Reserved parts',
  generate_shift_report: 'Shift report',
}

function eventLabel(event: ToolEvent): string {
  const name = TOOL_LABELS[event.name] ?? event.name
  if (event.confirmed === false) return `${name} declined`
  if (!event.ok) return `${name} failed`
  return event.confirmed ? `${name} confirmed` : name
}

function eventLamp(event: ToolEvent): string {
  if (event.confirmed === false || !event.ok) return 'bg-signal-red'
  return event.confirmed ? 'bg-hivis' : 'bg-signal-green'
}

const MARKDOWN = cn(
  'text-[15px] leading-relaxed',
  '[&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:my-2.5',
  '[&_ul]:my-2.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2.5 [&_ol]:list-decimal [&_ol]:pl-5',
  '[&_li]:my-1 [&_li]:marker:text-primary/60 [&_strong]:font-semibold [&_strong]:text-primary',
  '[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:text-[0.9em]',
  '[&_blockquote]:border-l-2 [&_blockquote]:border-hivis [&_blockquote]:pl-3',
)

export function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'notice') {
    return <p className="text-center text-xs font-medium text-muted-foreground">{message.text}</p>
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-[15px] whitespace-pre-wrap text-primary-foreground shadow-sm">
          {message.text}
        </p>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 space-y-2">
        {message.events && message.events.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Tools used">
            {message.events.map((event, index) => (
              <li
                key={index}
                className="flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-0.5 text-xs text-muted-foreground"
              >
                <span className={cn('size-1.5 rounded-full', eventLamp(event))} aria-hidden />
                {eventLabel(event)}
              </li>
            ))}
          </ul>
        )}
        <div
          className={cn('rounded-2xl rounded-tl-sm border bg-card px-5 py-4 shadow-sm', MARKDOWN)}
        >
          <Markdown>{message.text}</Markdown>
        </div>
      </div>
    </div>
  )
}
