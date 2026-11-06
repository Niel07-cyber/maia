import type { PendingAction } from '../api'

type Props = {
  actions: PendingAction[]
  busy: boolean
  onAnswer: (approved: boolean) => void
}

export function PendingCard({ actions, busy, onAnswer }: Props) {
  return (
    <section className="pending" aria-label="Needs your confirmation">
      <h2>Needs your confirmation</h2>
      <ul>
        {actions.map((action, index) => (
          <li key={index}>{action.description}</li>
        ))}
      </ul>
      <div className="pending-buttons">
        <button type="button" className="primary" disabled={busy} onClick={() => onAnswer(true)}>
          Confirm
        </button>
        <button type="button" disabled={busy} onClick={() => onAnswer(false)}>
          Cancel
        </button>
      </div>
    </section>
  )
}
