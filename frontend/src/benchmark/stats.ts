import type { Report, Run } from './types'

/** "openai/gpt-5.4-mini" -> "gpt-5.4-mini" */
export function modelName(model: string): string {
  return model.split('/').pop() ?? model
}

export function runsFor(report: Report, scenarioId: string, model: string): Run[] {
  return report.runs
    .filter((run) => run.scenario_id === scenarioId && run.model === model)
    .sort((a, b) => a.repeat - b.repeat)
}

export type BeforeAfter = {
  scenarioId: string
  title: string
  model: string
  before: { passed: number; runs: number }
  after: { passed: number; runs: number }
}

/** Compare the main run with a later check on the scenarios the check covers. */
export function beforeAfter(before: Report, after: Report): BeforeAfter[] {
  const rows: BeforeAfter[] = []
  for (const scenario of after.scenarios) {
    for (const summary of after.summaries) {
      const old = runsFor(before, scenario.id, summary.model)
      const recent = runsFor(after, scenario.id, summary.model)
      if (old.length === 0 || recent.length === 0) continue
      rows.push({
        scenarioId: scenario.id,
        title: scenario.title,
        model: summary.model,
        before: { passed: old.filter((run) => run.passed).length, runs: old.length },
        after: { passed: recent.filter((run) => run.passed).length, runs: recent.length },
      })
    }
  }
  return rows
}
