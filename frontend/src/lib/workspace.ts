// Builds the side panel's state from the tools the agent has run so far.
// The chat text is for people; the tool results are the facts, so the panel reads those.

import type { AssetInfo, ReservationInfo, StepLogged, ToolEvent, WorkOrderInfo } from '@/api'

export type WorkOrder = WorkOrderInfo & { parts: ReservationInfo[] }

export type Workspace = {
  asset: AssetInfo | null
  steps: StepLogged[]
  workOrders: WorkOrder[]
}

export const EMPTY_WORKSPACE: Workspace = { asset: null, steps: [], workOrders: [] }

type WorkOrderResult = { work_order: WorkOrderInfo; reservations: ReservationInfo[] }

export function applyEvents(workspace: Workspace, events: ToolEvent[]): Workspace {
  let { asset, steps, workOrders } = workspace
  for (const event of events) {
    if (!event.ok || event.result == null) continue
    switch (event.name) {
      case 'get_asset':
        asset = event.result as AssetInfo
        break
      case 'log_step':
        steps = [...steps, event.result as StepLogged]
        break
      case 'create_work_order': {
        const { work_order, reservations } = event.result as WorkOrderResult
        workOrders = [...workOrders, { ...work_order, parts: reservations }]
        break
      }
      case 'reserve_parts': {
        const reservation = event.result as ReservationInfo
        workOrders = workOrders.map((order) =>
          order.work_order_id === reservation.work_order_id
            ? { ...order, parts: [...order.parts, reservation] }
            : order,
        )
        break
      }
    }
  }
  return { asset, steps, workOrders }
}
