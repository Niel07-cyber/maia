import { describe, expect, it } from 'vitest'

import type { ToolEvent } from '@/api'

import { applyEvents, EMPTY_WORKSPACE } from './workspace'

const asset = {
  asset_id: 'RV200-014-B2',
  vehicle_id: 'RV200-014',
  vehicle_status: 'in_service',
  name: 'Bogie B2 brake unit',
  open_work_orders: 0,
}

const step = {
  step_log_id: 1,
  procedure_code: 'PROC-BRK-01',
  step: 4,
  reading: 4,
  unit: 'mm',
  assessment: null,
}

const workOrder = {
  work_order_id: 7,
  vehicle_id: 'RV200-014',
  asset_id: 'RV200-014-B2',
  procedure_code: 'PROC-BRK-01',
  priority: 'high',
  description: 'Replace brake pads',
}

function event(name: string, result: unknown, ok = true): ToolEvent {
  return { name, ok, confirmed: null, result }
}

describe('applyEvents', () => {
  it('collects the asset, logged steps and work orders with their parts', () => {
    const workspace = applyEvents(EMPTY_WORKSPACE, [
      event('get_asset', asset),
      event('log_step', step),
      event('create_work_order', {
        work_order: workOrder,
        reservations: [{ work_order_id: 7, part_number: 'BP-2207', quantity: 2 }],
      }),
      event('reserve_parts', { work_order_id: 7, part_number: 'CS-1130', quantity: 1 }),
    ])

    expect(workspace.asset?.asset_id).toBe('RV200-014-B2')
    expect(workspace.steps).toHaveLength(1)
    expect(workspace.workOrders[0].parts.map((part) => part.part_number)).toEqual([
      'BP-2207',
      'CS-1130',
    ])
  })

  it('ignores failed tools and tools the panel does not show', () => {
    const workspace = applyEvents(EMPTY_WORKSPACE, [
      event('log_step', { error: 'Readings must be in mm.' }, false),
      event('search_manual', []),
    ])

    expect(workspace).toEqual(EMPTY_WORKSPACE)
  })
})
