import Markdown from 'react-markdown'

import type { ToolEvent } from '@/api'
import { Badge } from '@/components/ui/badge'
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
  if (event.confirmed === false) return `${name} · declined`
  if (!event.ok) return `${name} · failed`
  return event.confirmed ? `${name} · confirmed` : name
}

const MARKDOWN = cn(
  'text-[15px] leading-relaxed',
  '[&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:my-2',
  '[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5',
  '[&_li]:my-0.5 [&_strong]:font-semibold',
  '[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:text-[0.9em]',
  '[&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground',
)

export function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'notice') {
    return <p className="text-center text-xs text-muted-foreground">{message.text}</p>
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-[15px] whitespace-pre-wrap text-primary-foreground">
          {message.text}
        </p>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
        M
      </div>
      <div className="min-w-0 flex-1 space-y-2 pt-0.5">
        {message.events && message.events.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Tools used">
            {message.events.map((event, index) => (
              <li key={index}>
                <Badge
                  variant={event.ok ? 'secondary' : 'destructive'}
                  className="font-normal text-muted-foreground"
                >
                  {eventLabel(event)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
        <div className={MARKDOWN}>
          <Markdown>{message.text}</Markdown>
        </div>
      </div>
    </div>
  )
}
