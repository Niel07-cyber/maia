// The JSON written by `python -m maia.benchmark` (see backend/maia/benchmark/benchmark.py).

export type Check = { name: string; passed: boolean; detail: string; safety: boolean }

export type RunTurn = {
  technician: string
  reply: string
  tools: { name: string; ok: boolean; confirmed: boolean | null }[]
  pending: string[]
  seconds: number
}

export type Run = {
  agent: string
  model: string
  scenario_id: string
  repeat: number
  passed: boolean
  safety_violations: string[]
  checks: Check[]
  seconds: number
  llm_calls: number
  cost_usd: number | null
  error: string | null
  turns: RunTurn[]
}

export type Summary = {
  agent: string
  model: string
  runs: number
  passed: number
  pass_rate: number
  safety_violations: number
  mean_seconds: number
  mean_cost_usd: number | null
  total_cost_usd: number | null
}

export type ScenarioInfo = { id: string; title: string; description: string }

export type Report = {
  generated_at: string
  repeats: number
  scenarios: ScenarioInfo[]
  summaries: Summary[]
  runs: Run[]
}
