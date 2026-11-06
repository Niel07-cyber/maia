import Markdown from 'react-markdown'

import type { ToolEvent } from '../api'

export type Message = {
  id: number
  role: 'user' | 'assistant' | 'notice'
  text: string
  events?: ToolEvent[]
}

function eventLabel(event: ToolEvent): string {
  if (event.confirmed === false) return 'declined'
  if (!event.ok) return 'refused'
  return event.confirmed ? 'confirmed' : 'ok'
}

export function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'notice') {
    return <p className="notice">{message.text}</p>
  }
  return (
    <div className={`bubble ${message.role}`}>
      {message.events && message.events.length > 0 && (
        <ul className="events" aria-label="Tools used">
          {message.events.map((event, index) => (
            <li key={index} className={`event ${eventLabel(event)}`}>
              {event.name} · {eventLabel(event)}
            </li>
          ))}
        </ul>
      )}
      {message.role === 'assistant' ? <Markdown>{message.text}</Markdown> : <p>{message.text}</p>}
    </div>
  )
}
