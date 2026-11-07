import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BenchmarkPage } from './BenchmarkPage'
import type { Report, Run } from './types'

function run(model: string, repeat: number, passed: boolean): Run {
  return {
    agent: 'explicit',
    model,
    scenario_id: 'door',
    repeat,
    passed,
    safety_violations: [],
    checks: [
      {
        name: 'called check_stock',
        passed,
        detail: passed ? 'tools used: check_stock' : 'tools used: log_step',
        safety: false,
      },
    ],
    seconds: 12.5,
    llm_calls: 4,
    cost_usd: 0.01,
    error: null,
    turns: [
      {
        technician: 'Obstacle detection failed.',
        reply: 'Replace sensor **DS-450**.',
        tools: [{ name: 'log_step', ok: true, confirmed: null }],
        pending: [],
        seconds: 5,
      },
    ],
  }
}

const REPORT: Report = {
  generated_at: '2026-11-06T16:00:00+00:00',
  repeats: 2,
  scenarios: [{ id: 'door', title: 'Part out of stock', description: 'The sensor has no stock.' }],
  summaries: [
    {
      agent: 'explicit',
      model: 'openai/gpt-5.4-mini',
      runs: 2,
      passed: 1,
      pass_rate: 0.5,
      safety_violations: 0,
      mean_seconds: 12.5,
      mean_cost_usd: 0.01,
      total_cost_usd: 0.02,
    },
  ],
  runs: [run('openai/gpt-5.4-mini', 1, false), run('openai/gpt-5.4-mini', 2, true)],
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url.endsWith('results.json')
        ? new Response(JSON.stringify(REPORT))
        : new Response('not found', { status: 404 }),
    ),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Benchmark page', () => {
  it('summarises each model', async () => {
    render(<BenchmarkPage />)

    expect(await screen.findByRole('rowheader', { name: 'Runs passed' })).toBeInTheDocument()
    expect(screen.getByText('1/2')).toBeInTheDocument()
    expect(screen.getAllByText('gpt-5.4-mini').length).toBeGreaterThan(0)
  })

  it('shows the checks and conversation of a selected run', async () => {
    render(<BenchmarkPage />)

    await userEvent.click(
      await screen.findByRole('button', { name: 'gpt-5.4-mini, run 1: failed' }),
    )

    const detail = screen.getByRole('article', { name: 'Run detail' })
    expect(detail).toHaveTextContent('tools used: log_step')
    expect(detail).toHaveTextContent('Obstacle detection failed.')
  })

  it('explains when the results cannot be loaded', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('', { status: 500 })),
    )

    render(<BenchmarkPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load')
  })
})
