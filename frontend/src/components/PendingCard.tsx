import type { PendingAction } from '@/api'
import { Button } from '@/components/ui/button'

type Props = {
  actions: PendingAction[]
  busy: boolean
  onAnswer: (approved: boolean) => void
}

/** Styled like a lockout tag: nothing happens until a person signs it off. */
export function PendingCard({ actions, busy, onAnswer }: Props) {
  return (
    <section
      aria-label="Needs your confirmation"
      className="ml-11 overflow-hidden rounded-2xl border bg-card shadow-md"
    >
      <div
        aria-hidden
        className="h-2.5 bg-[repeating-linear-gradient(-45deg,var(--hivis)_0_12px,var(--hivis-foreground)_12px_24px)]"
      />
      <div className="p-5">
        <h2 className="font-display text-sm font-semibold text-ink">Needs your confirmation</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          MAIA changes nothing until you confirm.
        </p>
        <ul className="mt-4 space-y-2">
          {actions.map((action, index) => (
            <li
              key={index}
              className="rounded-lg border-l-4 border-hivis bg-muted/60 px-3 py-2 text-[15px]"
            >
              {action.description}
            </li>
          ))}
        </ul>
        <div className="mt-5 flex gap-2">
          <Button disabled={busy} onClick={() => onAnswer(true)}>
            Confirm
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => onAnswer(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </section>
  )
}
