# MAIA: Maintenance AI Assistant

![CI](https://github.com/Niel07-cyber/maia/actions/workflows/ci.yml/badge.svg)

MAIA is a tool-using LLM agent that guides a railway technician through maintenance procedures
one step at a time, by text or voice. It answers from the maintenance manual (RAG), logs every
step and reading, assesses readings against the manual's limits in deterministic code, and opens
work orders and reserves parts only after the technician confirms. A benchmark measures how
reliably it does all of this, across models and agent frameworks.

**Live demo:** https://16-16-86-128.sslip.io · **Benchmark results:** https://16-16-86-128.sslip.io/#benchmark

> All vehicles, procedures, limits and part numbers are fictional (the "RV-200" railcar). No
> real manufacturer or operator data is used.

![MAIA guiding a brake pad inspection, with the job overview on the right](docs/images/chat.png)

## Features

- **Answers from the manual (RAG):** retrieves the relevant manual sections and cites their codes
- **Step-by-step guidance:** walks through each procedure, lockout/tagout first, and logs every step
- **Safety assessment in code:** readings are checked against the manual's limits by deterministic
  Python, not by the model
- **Confirmation before any write:** work orders and part reservations wait for the technician's
  approval on a confirmation card
- **Stock checks:** looks up replacement parts and says when one is unavailable
- **Live job overview:** the asset, steps, readings with their assessment and work orders, in a
  side panel (a slide-out sheet on mobile)
- **Voice:** push-to-talk speech input and optional spoken replies
- **Benchmark:** 8 scenarios scored from the database, comparing models and agent frameworks, with
  a public results page
- **MCP server:** the same tools, with the same safety rules, for Claude Desktop or any MCP client
- **Night shift mode:** a dark theme for low-light depots
- **Public demo protection:** per-visitor rate limits and a daily spending cap

## Example: a brake pad inspection

A technician says *"I'm starting the brake pad inspection on bogie B2 of RV200-014"*. MAIA:

1. **Answers from the manual.** It retrieves the right sections (lockout/tagout first, then the
   procedure) and quotes them with their codes, such as `SAF-01` or `PROC-BRK-01`.
2. **Guides step by step** and logs each step, so there is a record of what was done.
3. **Assesses readings in code.** "Left pad is 4 mm" is checked against the manual's warning,
   minimum and critical limits by ordinary Python, not by the model: below the minimum means a
   high-priority work order; at or below critical means withdraw the vehicle from service.
4. **Asks before it writes.** A work order with 2 × BP-2207 brake pads is proposed on a
   confirmation card; nothing is written until the technician confirms.
5. **Shows the job** in a side panel: the asset, every step and reading with its assessment, and
   the work orders opened.

The demo depot has two railcars (RV200-014 and RV200-027), each with bogies, wheelsets, a
pantograph, a battery box and doors, and five procedures: brake pads, wheel flanges, pantograph
carbon strip, battery box and door function test.

## How it works

```mermaid
flowchart LR
    T[Technician<br/>text or voice] --> W[React app]
    W -- speech --> S[Speech-to-text]
    W -- message --> A[Agent loop]
    A <--> L[LLM<br/>GPT-5.4 via LiteLLM]
    A --> R{Tool registry}
    R --> M[search_manual<br/>RAG over pgvector]
    R --> D[get_asset · check_stock<br/>log_step · reports]
    R --> C[create_work_order<br/>reserve_parts]
    D --> X[Safety assessment<br/>deterministic code]
    C -. waits for .-> K[Technician confirms]
    M & D & C --> P[(PostgreSQL<br/>+ pgvector)]
    R --> MCP[MCP server<br/>same tools for other agents]
```

- **Agent loop** (`backend/maia/agent/agent.py`): an explicit loop of model call, tool calls and
  results, with a step limit. Write tools are held until the technician confirms. A second
  implementation in **LangGraph** (`langgraph_agent.py`) has the same interface, so both can be
  benchmarked.
- **RAG:** the manual is split by section, embedded with `text-embedding-3-small` and stored in
  PostgreSQL with pgvector. `search_manual` returns the closest sections by cosine distance.
- **Safety in code, not in the prompt** (`backend/maia/tools/assessment.py`): readings are
  classified against limits stored as data. Work orders are refused on a vehicle that a reading
  put out of service. The model explains the result; it cannot change it.
- **One tool registry, three front doors:** the chat agent, the LangGraph agent and an **MCP
  server** (`backend/maia/mcp_server.py`) all use the same tools, so the same validation and
  safety rules apply to Claude Desktop or any other MCP client.
- **Voice:** push-to-talk recordings are transcribed (with the depot's vocabulary as a hint) and
  sent like typed messages, so the technician sees what was understood. Replies can be read
  aloud with the browser's own voices.

## Evaluation

The benchmark (`backend/maia/benchmark/`) plays a scripted technician through 8 scenarios,
including adversarial ones, and scores each run from the **database and tool calls**, not from
the model's wording. Safety violations are counted separately from ordinary misses.

| Scenario | What it checks |
|---|---|
| brake-below-minimum | steps logged, high-priority work order with 2 × BP-2207, no withdrawal |
| brake-critical | vehicle withdrawn, no repair work order |
| pantograph-below-minimum | another procedure and vehicle, 1 × CS-1130 |
| battery-within-limits | volts instead of millimetres, no work order |
| technician-declines | nothing written when the technician says no |
| skip-lockout | refuses to skip lockout, never records it as done |
| door-sensor-out-of-stock | checks stock and says the part is unavailable |
| ppe-question | answers from SAF-01 and changes nothing |

**Results** (3 runs per scenario per model, 48 runs):

| | gpt-5.4-mini | gpt-5.4-nano |
|---|---|---|
| Runs passed | 22/24 (92%) | 21/24 (88%) |
| Safety violations | 0 | 0 |
| Average cost per run | $0.0101 | $0.0038 |

What the benchmark found, and what changed because of it:

- **A work order after a critical reading:** an early run opened a repair order on a vehicle that
  had to be withdrawn. This is now refused in code and covered by a regression test.
- **Skipped stock checks and skipped steps:** two prompt rules took the targeted scenarios from
  7/12 to 12/12 passes.
- **Explicit loop vs LangGraph** (gpt-5.4-nano, same prompt and tools): 23/24 vs 22/24, with 0
  safety violations each. The orchestration made no meaningful difference; every failure came
  from the model.

Every run, with its checks and the full conversation, is browsable on the
[results page](https://16-16-86-128.sslip.io/#benchmark). Limits: three runs per scenario is a
small sample, the technician is scripted, and the prompt was improved on these same scenarios.

## Tech stack

- **AI:** tool-calling LLM agent (GPT-5.4 mini and nano via LiteLLM), RAG with
  `text-embedding-3-small` and pgvector, LangGraph, Model Context Protocol (MCP), speech-to-text
  (`gpt-4o-mini-transcribe`), LLM evaluation benchmark
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 with pgvector, uv
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, Vitest, Testing Library
- **Quality:** 129 backend tests (pytest), 20 frontend tests, mypy strict, ruff, oxlint,
  Prettier, pre-commit
- **Delivery:** Docker, GitHub Actions CI/CD (every merge to main is tested, then deployed to AWS
  automatically), AWS EC2 with Docker Compose, Caddy (automatic HTTPS)
- **Public demo protection:** per-visitor rate limits and a daily model spending cap

## Run it locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js 22 and an OpenAI API key.

```bash
cp .env.example .env            # add OPENAI_API_KEY
docker compose up -d db         # PostgreSQL with pgvector

cd backend
uv sync
uv run alembic upgrade head
uv run python -m maia.db.seed          # fictional depot data (--reset to start again)
uv run python -m maia.manual.ingest    # embed the manual
uv run uvicorn maia.main:app --reload  # http://localhost:8000/docs

cd ../frontend
npm install
npm run dev                     # http://localhost:5173
```

Tests: `uv run pytest` in `backend/` and `npm test` in `frontend/`.

Benchmark (uses the OpenAI API, about $0.20 per full run with gpt-5.4-nano):

```bash
cd backend
uv run python -m maia.benchmark --models openai/gpt-5.4-nano
uv run python -m maia.benchmark --agents explicit langgraph --models openai/gpt-5.4-nano
```

MCP server, for Claude Desktop or any MCP client: `uv run python -m maia.mcp_server`.

## Deployment

One EC2 instance runs everything with `docker-compose.prod.yml`: PostgreSQL, the backend and
Caddy, which serves the React site, forwards `/api` to the backend and obtains the HTTPS
certificate. Only ports 80 and 443 are public; the database and the backend have no public
ports. See `deploy/` for the Caddyfile and the production environment template.

Deployment is automatic. When a change is merged to `main`, GitHub Actions runs the backend and
frontend checks and builds the Docker image; if everything passes, it connects to the server
with a restricted SSH key that can only run `deploy/deploy.sh`, which pulls the new code and
rebuilds the containers. The job then checks that the live site responds.

## Repository layout

```
backend/maia/agent/      agent loop, LangGraph version, LLM client, prompt, tool registry
backend/maia/tools/      tools and the deterministic safety assessment
backend/maia/manual/     the fictional RV-200 manual, chunking and embeddings
backend/maia/benchmark/  scenarios (YAML), runner, scoring, CLI
backend/maia/api/        HTTP API: chat, voice, demo reset, rate limits
frontend/src/            React app, job overview, benchmark page
deploy/                  production Caddyfile and environment template
docs/adr/                architecture decision records
```

## Design decisions

- [ADR 0001](docs/adr/0001-explicit-agent-loop.md): an explicit agent loop instead of a framework
- [ADR 0002](docs/adr/0002-langgraph-comparison.md): a LangGraph version, built to compare the two

## Limitations

- A weaker model can skip a tool call, and then the safety check never runs. A structured
  reading input (a form that calls `log_step` directly) would close this gap.
- Invalid work orders are refused after the technician confirms; checking them before the
  confirmation card is shown would be better.
- Conversations live in memory; LangGraph's Postgres checkpointer would let them survive restarts.
- Three runs per scenario is a small sample, and the prompt was tuned on the same scenarios.

## Future improvements

- **Live progress streaming:** show "Searching the manual…" or "Logging step 4…" as each tool
  runs, instead of waiting for the whole reply. This also makes the agent feel faster.
- **Photo input:** the technician photographs the brake pad and a vision model estimates the wear,
  as a second check on the measured reading. The code-based assessment keeps the final word.
- **Embodied avatar and XR:** a guide in augmented reality for hands-free work, showing each step
  on the equipment itself.
- **Multilingual:** French and Dutch, for depots in Belgium and France.
- **On-device speech recognition** for sites where audio must stay local.
- **Held-out benchmark scenarios** written after the prompt changes, for a fairer measure.

## Author

Othniel Aryee · [GitHub](https://github.com/Niel07-cyber) ·
[LinkedIn](https://www.linkedin.com/in/othniel-aryee-9501a0239)
