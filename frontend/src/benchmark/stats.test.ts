import { describe, expect, it } from 'vitest'

import { beforeAfter, modelName, runsFor } from './stats'
import type { Report, Run } from './types'

function run(scenario_id: string, model: string, repeat: number, passed: boolean): Run {
  return {
    agent: 'explicit',
    model,
    scenario_id,
    repeat,
    passed,
    safety_violations: [],
    checks: [],
    seconds: 1,
    llm_calls: 1,
    cost_usd: 0.001,
    error: null,
    turns: [],
  }
}

function report(runs: Run[], scenarios = ['door']): Report {
  const models = [...new Set(runs.map((r) => r.model))]
  return {
    generated_at: '2026-11-06T16:00:00+00:00',
    repeats: 3,
    scenarios: scenarios.map((id) => ({ id, title: id, description: '' })),
    summaries: models.map((model) => ({
      agent: 'explicit',
      model,
      runs: 0,
      passed: 0,
      pass_rate: 0,
      safety_violations: 0,
      mean_seconds: 0,
      mean_cost_usd: 0,
      total_cost_usd: 0,
    })),
    runs,
  }
}

describe('benchmark stats', () => {
  it('shortens model names', () => {
    expect(modelName('openai/gpt-5.4-mini')).toBe('gpt-5.4-mini')
  })

  it('returns the runs of one scenario and model in repeat order', () => {
    const data = report([
      run('door', 'm', 2, true),
      run('door', 'm', 1, false),
      run('ppe', 'm', 1, true),
    ])

    expect(runsFor(data, 'door', 'm').map((r) => r.repeat)).toEqual([1, 2])
  })

  it('compares a later check with the main run', () => {
    const before = report(
      [run('door', 'm', 1, false), run('door', 'm', 2, true), run('ppe', 'm', 1, true)],
      ['door', 'ppe'],
    )
    const after = report([run('door', 'm', 1, true), run('door', 'm', 2, true)])

    expect(beforeAfter(before, after)).toEqual([
      {
        scenarioId: 'door',
        title: 'door',
        model: 'm',
        before: { passed: 1, runs: 2 },
        after: { passed: 2, runs: 2 },
      },
    ])
  })
})
