import { CircleCheck, OctagonAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Band, Priority, StepLogged } from '@/api'
import { Badge } from '@/components/ui/badge'
import type { Workspace } from '@/lib/workspace'
import { cn } from '@/lib/utils'

const BANDS: Record<Band, { label: string; className: string }> = {
  within_limits: {
    label: 'Within limits',
    className: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  },
  below_warning: {
    label: 'Below warning',
    className: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  },
  below_minimum: {
    label: 'Below minimum',
    className: 'bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300',
  },
  at_or_below_critical: {
    label: 'Critical',
    className: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
  },
}

const PRIORITIES: Record<Priority, string> = {
  high: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
  medium: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  low: 'bg-muted text-muted-foreground',
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h2>
      {children}
    </section>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>
}

function StepRow({ step }: { step: StepLogged }) {
  const band = step.assessment ? BANDS[step.assessment.band] : null
  return (
    <li className="flex items-center justify-between gap-3 py-2 text-sm">
      <span>
        <span className="font-medium">Step {step.step}</span>
        <span className="text-muted-foreground"> · {step.procedure_code}</span>
      </span>
      {step.reading === null ? (
        <CircleCheck className="size-4 text-emerald-600" aria-label="Done" />
      ) : (
        <span className="flex items-center gap-2">
          <span className="tabular-nums">
            {step.reading} {step.unit}
          </span>
          {band && <Badge className={cn('border-0', band.className)}>{band.label}</Badge>}
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
    <aside aria-label="Job overview" className={cn('space-y-8 overflow-y-auto p-6', className)}>
      {withdraw && (
        <div
          role="status"
          className="flex gap-2 rounded-lg bg-red-100 p-3 text-sm text-red-900 dark:bg-red-950 dark:text-red-200"
        >
          <OctagonAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            <strong>Withdraw from service.</strong> A reading is at or below the critical limit.
          </span>
        </div>
      )}

      <Section title="Asset">
        {asset ? (
          <div className="space-y-1">
            <p className="font-medium">{asset.name}</p>
            <p className="text-sm text-muted-foreground">
              {asset.asset_id} · {asset.vehicle_id}
            </p>
            <Badge
              className={cn(
                'border-0',
                asset.vehicle_status === 'in_service'
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
              )}
            >
              {asset.vehicle_status === 'in_service' ? 'In service' : 'Out of service'}
            </Badge>
          </div>
        ) : (
          <Empty>Tell MAIA which vehicle you are working on.</Empty>
        )}
      </Section>

      <Section title="Steps and readings">
        {steps.length > 0 ? (
          <ul className="divide-y">
            {steps.map((step) => (
              <StepRow key={step.step_log_id} step={step} />
            ))}
          </ul>
        ) : (
          <Empty>Logged steps will appear here.</Empty>
        )}
      </Section>

      <Section title="Work orders">
        {workOrders.length > 0 ? (
          <ul className="space-y-3">
            {workOrders.map((order) => (
              <li key={order.work_order_id} className="rounded-lg border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">WO-{order.work_order_id}</span>
                  <Badge className={cn('border-0 capitalize', PRIORITIES[order.priority])}>
                    {order.priority}
                  </Badge>
                </div>
                <p className="mt-1 text-muted-foreground">{order.description}</p>
                {order.parts.length > 0 && (
                  <p className="mt-2 text-xs">
                    Reserved:{' '}
                    {order.parts.map((part) => `${part.quantity} × ${part.part_number}`).join(', ')}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Empty>No work orders opened in this session.</Empty>
        )}
      </Section>
    </aside>
  )
}
