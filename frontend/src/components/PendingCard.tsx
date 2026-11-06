import { ShieldAlert } from 'lucide-react'

import type { PendingAction } from '@/api'
import { Button } from '@/components/ui/button'

type Props = {
  actions: PendingAction[]
  busy: boolean
  onAnswer: (approved: boolean) => void
}

export function PendingCard({ actions, busy, onAnswer }: Props) {
  return (
    <section
      aria-label="Needs your confirmation"
      className="ml-10 rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-950/40"
    >
      <div className="flex items-center gap-2 text-amber-900 dark:text-amber-200">
        <ShieldAlert className="size-4" aria-hidden />
        <h2 className="text-sm font-semibold">Needs your confirmation</h2>
      </div>
      <p className="mt-1 text-xs text-amber-800/80 dark:text-amber-200/70">
        MAIA changes nothing until you confirm.
      </p>
      <ul className="mt-3 space-y-1 text-sm">
        {actions.map((action, index) => (
          <li key={index}>{action.description}</li>
        ))}
      </ul>
      <div className="mt-4 flex gap-2">
        <Button size="sm" disabled={busy} onClick={() => onAnswer(true)}>
          Confirm
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onAnswer(false)}>
          Cancel
        </Button>
      </div>
    </section>
  )
}
