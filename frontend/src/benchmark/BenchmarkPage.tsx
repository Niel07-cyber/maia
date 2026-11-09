import { useEffect, useState, type ReactNode } from 'react'
import Markdown from 'react-markdown'

import { cn } from '@/lib/utils'

import { beforeAfter, modelName, runsFor } from './stats'
import type { Report, Run } from './types'

const RESULTS_URL = `${import.meta.env.BASE_URL}benchmark/results.json`
const CHECK_URL = `${import.meta.env.BASE_URL}benchmark/prompt-v2-check.json`
const FRAMEWORK_URL = `${import.meta.env.BASE_URL}benchmark/framework-comparison.json`

const AGENT_NAMES: Record<string, string> = { explicit: 'Explicit loop', langgraph: 'LangGraph' }

async function load(url: string): Promise<Report> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Could not load ${url} (${response.status})`)
  return (await response.json()) as Report
}

function money(value: number | null, digits = 4): string {
  return value === null ? 'unknown' : `$${value.toFixed(digits)}`
}

export function BenchmarkPage() {
  const [report, setReport] = useState<Report | null>(null)
  const [check, setCheck] = useState<Report | null>(null)
  const [frameworks, setFrameworks] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Run | null>(null)

  useEffect(() => {
    load(RESULTS_URL)
      .then(setReport)
      .catch((caught: Error) => setError(caught.message))
    // The follow-up check is optional: the page works without it.
    load(CHECK_URL)
      .then(setCheck)
      .catch(() => setCheck(null))
    load(FRAMEWORK_URL)
      .then(setFrameworks)
      .catch(() => setFrameworks(null))
  }, [])

  if (error) {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {error}
      </p>
    )
  }
  if (!report) {
    return <p className="p-8 text-sm text-muted-foreground">Loading the benchmark results…</p>
  }

  const models = report.summaries.map((summary) => summary.model)
  const comparison = check ? beforeAfter(report, check) : []

  return (
    <div className="mx-auto max-w-5xl space-y-12 px-4 py-10 sm:px-6">
      <header className="max-w-2xl">
        <h2 className="font-display text-3xl leading-tight font-semibold tracking-tight text-primary">
          How MAIA was evaluated
        </h2>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
          {report.scenarios.length} scripted technician scenarios, each run {report.repeats} times
          per model on freshly reset demo data. Every run is scored from the database and the tool
          calls, not from how the reply is worded. Run on{' '}
          {new Date(report.generated_at).toLocaleDateString('en-GB', { dateStyle: 'long' })}.
        </p>
      </header>

      <Section title="Results by model">
        <div className="overflow-x-auto rounded-2xl border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="px-5 py-3 font-medium text-muted-foreground">Metric</th>
                {report.summaries.map((summary) => (
                  <th key={summary.model} className="px-5 py-3 font-display font-semibold">
                    {modelName(summary.model)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              <Row label="Runs passed">
                {report.summaries.map((s) => (
                  <td key={s.model} className="px-5 py-3">
                    <span className="font-semibold">
                      {s.passed}/{s.runs}
                    </span>{' '}
                    <span className="text-muted-foreground">
                      ({Math.round(s.pass_rate * 100)}%)
                    </span>
                  </td>
                ))}
              </Row>
              <Row label="Safety violations">
                {report.summaries.map((s) => (
                  <td
                    key={s.model}
                    className={cn(
                      'px-5 py-3 font-semibold',
                      s.safety_violations === 0 ? 'text-signal-green' : 'text-signal-red',
                    )}
                  >
                    {s.safety_violations}
                  </td>
                ))}
              </Row>
              <Row label="Average time per run">
                {report.summaries.map((s) => (
                  <td key={s.model} className="px-5 py-3 tabular-nums">
                    {s.mean_seconds.toFixed(1)} s
                  </td>
                ))}
              </Row>
              <Row label="Average cost per run">
                {report.summaries.map((s) => (
                  <td key={s.model} className="px-5 py-3 tabular-nums">
                    {money(s.mean_cost_usd)}
                  </td>
                ))}
              </Row>
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="Every run"
        intro="Each lamp is one run. Select one to see what was checked and the conversation."
      >
        <div className="overflow-x-auto rounded-2xl border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="px-5 py-3 font-medium text-muted-foreground">Scenario</th>
                {models.map((model) => (
                  <th
                    key={model}
                    className="px-5 py-3 font-display font-semibold whitespace-nowrap"
                  >
                    {modelName(model)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {report.scenarios.map((scenario) => (
                <tr key={scenario.id} className="align-top">
                  <td className="px-5 py-4">
                    <p className="font-medium text-ink">{scenario.title}</p>
                    <p className="mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
                      {scenario.description}
                    </p>
                  </td>
                  {models.map((model) => (
                    <td key={model} className="px-5 py-4">
                      <div className="flex gap-2">
                        {runsFor(report, scenario.id, model).map((run) => (
                          <RunLamp
                            key={run.repeat}
                            run={run}
                            selected={selected === run}
                            onSelect={() => setSelected(selected === run ? null : run)}
                          />
                        ))}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selected && (
          <RunDetail
            run={selected}
            title={report.scenarios.find((s) => s.id === selected.scenario_id)?.title ?? ''}
          />
        )}
      </Section>

      <Section title="What the benchmark found">
        <div className="grid gap-4 md:grid-cols-3">
          <Finding title="Skipped stock checks">
            In the out-of-stock scenario, both models sometimes told the technician to replace the
            door sensor without checking that one was available. The store had none. A prompt rule
            now requires a stock check for every replacement part.
          </Finding>
          <Finding title="Two steps in one sentence">
            “Parking brake released, visual check fine” reports two procedure steps. The smaller
            model sometimes logged only one. The prompt now asks for each reported step to be
            logged.
          </Finding>
          <Finding title="A work order after a critical reading">
            In an earlier run, the larger model opened a repair order on a vehicle that had to be
            withdrawn. This is now refused in code, whatever the model does, and covered by a test.
          </Finding>
        </div>

        {comparison.length > 0 && (
          <div className="overflow-x-auto rounded-2xl border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="px-5 py-3 font-medium text-muted-foreground">
                    After the prompt fix
                  </th>
                  <th className="px-5 py-3 font-medium text-muted-foreground">Model</th>
                  <th className="px-5 py-3 font-medium text-muted-foreground">Before</th>
                  <th className="px-5 py-3 font-medium text-muted-foreground">After</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {comparison.map((row) => (
                  <tr key={`${row.scenarioId}-${row.model}`}>
                    <td className="px-5 py-3 font-medium">{row.title}</td>
                    <td className="px-5 py-3">{modelName(row.model)}</td>
                    <td className="px-5 py-3 tabular-nums">
                      {row.before.passed}/{row.before.runs}
                    </td>
                    <td className="px-5 py-3 font-semibold tabular-nums">
                      {row.after.passed}/{row.after.runs}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {frameworks && (
        <Section
          title="Explicit loop vs LangGraph"
          intro={`The same agent built twice: once as a plain loop, once with LangGraph. Same model (${modelName(frameworks.summaries[0]?.model ?? '')}), prompt, tools and safety code, so only the orchestration differs.`}
        >
          <div className="overflow-x-auto rounded-2xl border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="px-5 py-3 font-medium text-muted-foreground">Metric</th>
                  {frameworks.summaries.map((s) => (
                    <th key={s.agent} className="px-5 py-3 font-display font-semibold">
                      {AGENT_NAMES[s.agent] ?? s.agent}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                <Row label="Runs passed">
                  {frameworks.summaries.map((s) => (
                    <td key={s.agent} className="px-5 py-3 font-semibold">
                      {s.passed}/{s.runs}
                    </td>
                  ))}
                </Row>
                <Row label="Safety violations">
                  {frameworks.summaries.map((s) => (
                    <td
                      key={s.agent}
                      className={cn(
                        'px-5 py-3 font-semibold',
                        s.safety_violations === 0 ? 'text-signal-green' : 'text-signal-red',
                      )}
                    >
                      {s.safety_violations}
                    </td>
                  ))}
                </Row>
                <Row label="Average time per run">
                  {frameworks.summaries.map((s) => (
                    <td key={s.agent} className="px-5 py-3 tabular-nums">
                      {s.mean_seconds.toFixed(1)} s
                    </td>
                  ))}
                </Row>
                <Row label="Average cost per run">
                  {frameworks.summaries.map((s) => (
                    <td key={s.agent} className="px-5 py-3 tabular-nums">
                      {money(s.mean_cost_usd)}
                    </td>
                  ))}
                </Row>
              </tbody>
            </table>
          </div>
          <p className="max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            No meaningful difference. Both had zero safety violations, and the one-run gap in passes
            is within the run-to-run variation of the model. Every failure was the same kind in both
            versions: the model skipped logging a step or a stock check. The orchestration does not
            change how well the agent behaves; the model and the prompt do. LangGraph adds saved
            state and pause-and-resume for free, at the cost of more concepts; the plain loop is
            easier to read and debug.
          </p>
        </Section>
      )}

      <Section title="Limits of this benchmark">
        <ul className="max-w-2xl list-disc space-y-2 pl-5 text-[15px] leading-relaxed text-muted-foreground">
          <li>
            Three runs per scenario is a small sample. A failure that happens one time in ten can
            easily not appear: in an earlier run, the smaller model once failed to log a critical
            reading, so the safety check never ran.
          </li>
          <li>
            The technician is scripted, which makes runs reproducible but less varied than a real
            person. A second model playing the technician would test more phrasings.
          </li>
          <li>
            The prompt was improved using these scenarios. New scenarios written afterwards would
            show whether the improvement holds on cases it was not tuned for.
          </li>
        </ul>
      </Section>
    </div>
  )
}

function Section({
  title,
  intro,
  children,
}: {
  title: string
  intro?: string
  children: ReactNode
}) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="font-display text-lg font-semibold text-ink">{title}</h3>
        {intro && <p className="mt-1 text-sm text-muted-foreground">{intro}</p>}
      </div>
      {children}
    </section>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row" className="px-5 py-3 text-left font-medium text-muted-foreground">
        {label}
      </th>
      {children}
    </tr>
  )
}

function RunLamp({
  run,
  selected,
  onSelect,
}: {
  run: Run
  selected: boolean
  onSelect: () => void
}) {
  const unsafe = run.safety_violations.length > 0
  const status = unsafe ? 'safety violation' : run.passed ? 'passed' : 'failed'
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${modelName(run.model)}, run ${run.repeat}: ${status}`}
      title={`Run ${run.repeat}: ${status}`}
      className={cn(
        'size-5 rounded-full ring-offset-2 ring-offset-card transition outline-none focus-visible:ring-[3px] focus-visible:ring-ring',
        run.passed ? 'bg-signal-green' : unsafe ? 'bg-signal-red' : 'bg-signal-orange',
        selected && 'ring-[3px] ring-primary',
      )}
    />
  )
}

function RunDetail({ run, title }: { run: Run; title: string }) {
  return (
    <article aria-label="Run detail" className="rounded-2xl border bg-card p-5 shadow-sm">
      <h4 className="font-display text-base font-semibold text-ink">
        {title}, {modelName(run.model)}, run {run.repeat}
      </h4>
      <p className="mt-1 text-sm text-muted-foreground">
        {run.seconds.toFixed(1)} s, {run.llm_calls} model calls, {money(run.cost_usd)}
      </p>

      <ul className="mt-4 space-y-1.5 text-sm">
        {run.checks.map((check) => (
          <li key={check.name} className="flex gap-2">
            <span
              aria-hidden
              className={cn(
                'mt-1.5 size-2 shrink-0 rounded-full',
                check.passed
                  ? 'bg-signal-green'
                  : check.safety
                    ? 'bg-signal-red'
                    : 'bg-signal-orange',
              )}
            />
            <span>
              <span className="font-medium">{check.name}</span>
              <span className="text-muted-foreground">: {check.detail}</span>
              {!check.passed && <span className="sr-only"> (failed)</span>}
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-6 space-y-4 border-t pt-5">
        {run.turns.map((turn, index) => (
          <div key={index} className="space-y-2 text-sm">
            <p>
              <span className="font-semibold text-primary">Technician: </span>
              {turn.technician}
            </p>
            {turn.tools.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Tools:{' '}
                {turn.tools.map((tool) => tool.name + (tool.ok ? '' : ' (failed)')).join(', ')}
              </p>
            )}
            <div className="rounded-xl bg-muted/60 px-4 py-3 [&_p]:my-1.5 [&_strong]:font-semibold">
              <Markdown>{turn.reply}</Markdown>
            </div>
          </div>
        ))}
      </div>
    </article>
  )
}

function Finding({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border bg-card p-5 shadow-sm">
      <h4 className="text-sm font-semibold text-ink">{title}</h4>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{children}</p>
    </div>
  )
}
