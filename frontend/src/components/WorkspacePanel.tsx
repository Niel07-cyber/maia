import { OctagonAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Band, Priority, StepLogged } from '@/api'
import type { Workspace } from '@/lib/workspace'
import { cn } from '@/lib/utils'

// Each band is shown like a signal aspect: a coloured lamp and a plain label.
const BANDS: Record<Band, { label: string; lamp: string; text: string }> = {
  within_limits: { label: 'Within limits', lamp: 'bg-signal-green', text: 'text-signal-green' },
  below_warning: { label: 'Below warning', lamp: 'bg-signal-amber', text: 'text-signal-amber' },
  below_minimum: { label: 'Below minimum', lamp: 'bg-signal-orange', text: 'text-signal-orange' },
  at_or_below_critical: { label: 'Critical', lamp: 'bg-signal-red', text: 'text-signal-red' },
}

const PRIORITIES: Record<Priority, { label: string; edge: string; pill: string }> = {
  high: {
    label: 'High priority',
    edge: 'border-l-signal-red',
    pill: 'bg-signal-red/10 text-signal-red',
  },
  medium: {
    label: 'Medium priority',
    edge: 'border-l-signal-amber',
    pill: 'bg-signal-amber/15 text-[#9a6a00]',
  },
  low: {
    label: 'Low priority',
    edge: 'border-l-primary',
    pill: 'bg-secondary text-secondary-foreground',
  },
}

function Section({
  title,
  count,
  children,
}: {
  title: string
  count?: number
  children: ReactNode
}) {
  return (
    <section className="space-y-3">
      <h2 className="flex items-baseline gap-2 text-sm font-semibold text-ink">
        {title}
        {count ? <span className="text-xs font-medium text-muted-foreground">{count}</span> : null}
      </h2>
      {children}
    </section>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed px-4 py-3 text-sm text-muted-foreground">
      {children}
    </p>
  )
}

function StepRow({ step, showProcedure }: { step: StepLogged; showProcedure: boolean }) {
  const band = step.assessment ? BANDS[step.assessment.band] : null
  return (
    <li className="relative flex items-start justify-between gap-3 pb-4 pl-6 last:pb-0">
      <span
        aria-hidden
        className={cn(
          'absolute top-1 left-0 size-3 rounded-full ring-4 ring-card',
          band ? band.lamp : 'bg-signal-green',
        )}
      />
      <span className="text-sm leading-tight">
        <span className="block font-medium">Step {step.step}</span>
        {showProcedure && (
          <span className="text-xs text-muted-foreground">{step.procedure_code}</span>
        )}
      </span>
      {step.reading === null ? (
        <span className="text-xs font-medium text-signal-green">Done</span>
      ) : (
        <span className="text-right leading-tight">
          <span className="block font-display text-sm font-semibold tabular-nums">
            {step.reading} {step.unit}
          </span>
          {band && <span className={cn('text-xs font-medium', band.text)}>{band.label}</span>}
        </span>
      )}
    </li>
  )
}

export function WorkspacePanel({
  workspace,
  className,
}: {
  workspace: Workspace
  className?: string
}) {
  const { asset, steps, workOrders } = workspace
  const withdraw = steps.some((step) => step.assessment?.withdraw_from_service)

  return (
    <aside
      aria-label="Job overview"
      className={cn('space-y-7 overflow-y-auto bg-card p-6', className)}
    >
      {withdraw && (
        <div role="status" className="flex gap-3 rounded-xl bg-signal-red p-4 text-sm text-white">
          <OctagonAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
          <span>
            <strong className="block font-display text-sm">Withdraw from service</strong>A reading
            is at or below the critical limit. Notify the shift supervisor.
          </span>
        </div>
      )}

      <Section title="Asset">
        {asset ? (
          <div className="rounded-xl bg-chrome p-4 text-chrome-foreground">
            <p className="font-display text-base font-semibold">{asset.name}</p>
            <p className="mt-0.5 text-sm text-chrome-foreground/70">
              {asset.asset_id} on {asset.vehicle_id}
            </p>
            <p className="mt-3 flex items-center gap-2 text-sm font-medium">
              <span
                aria-hidden
                className={cn(
                  'size-2.5 rounded-full',
                  asset.vehicle_status === 'in_service' ? 'bg-signal-green' : 'bg-signal-red',
                )}
              />
              {asset.vehicle_status === 'in_service' ? 'In service' : 'Out of service'}
            </p>
          </div>
        ) : (
          <Empty>Tell MAIA which vehicle you are working on.</Empty>
        )}
      </Section>

      <Section title="Steps and readings" count={steps.length}>
        {steps.length > 0 ? (
          <ul className="relative before:absolute before:top-2 before:bottom-2 before:left-[5px] before:w-0.5 before:bg-border">
            {steps.map((step, index) => (
              <StepRow
                key={step.step_log_id}
                step={step}
                showProcedure={step.procedure_code !== steps[index - 1]?.procedure_code}
              />
            ))}
          </ul>
        ) : (
          <Empty>Each step you finish is logged here, with its reading.</Empty>
        )}
      </Section>

      <Section title="Work orders" count={workOrders.length}>
        {workOrders.length > 0 ? (
          <ul className="space-y-3">
            {workOrders.map((order) => (
              <li
                key={order.work_order_id}
                className={cn(
                  'rounded-xl border border-l-4 bg-card p-4 text-sm shadow-sm',
                  PRIORITIES[order.priority].edge,
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-display font-semibold">WO-{order.work_order_id}</span>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-xs font-semibold',
                      PRIORITIES[order.priority].pill,
                    )}
                  >
                    {PRIORITIES[order.priority].label}
                  </span>
                </div>
                <p className="mt-1.5 text-muted-foreground">{order.description}</p>
                {order.parts.length > 0 && (
                  <ul className="mt-3 flex flex-wrap gap-1.5">
                    {order.parts.map((part) => (
                      <li
                        key={part.part_number}
                        className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground"
                      >
                        {part.quantity} × {part.part_number}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Work orders you confirm appear here.</Empty>
        )}
      </Section>
    </aside>
  )
}
