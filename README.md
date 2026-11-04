# MAIA: Maintenance AI Assistant

![CI](https://github.com/Niel07-cyber/maia/actions/workflows/ci.yml/badge.svg)

An embodied, voice-driven LLM agent in WebXR that guides rail maintenance procedures and automates the surrounding workflow (work orders, parts reservations, shift reports), with an open benchmark comparing LLMs.

> All vehicle data, procedures and part numbers in this repository are fictional. No real manufacturer or operator data is used.

## Status

Work in progress.

## Run locally

Requirements: Docker Desktop. For development without Docker: uv.

    cp .env.example .env        # add your API keys
    docker compose up --build   # Postgres + backend on http://localhost:8000

Load or reset the fictional demo data:

    docker compose run --rm backend python -m maia.db.seed          # load
    docker compose run --rm backend python -m maia.db.seed --reset  # reset

Development with hot reload:

    docker compose up -d db
    cd backend
    uv sync
    uv run uvicorn maia.main:app --reload
    uv run pytest

## Repository layout

    backend/   FastAPI agent, tools, database
    frontend/  React and WebXR client
    bench/     Benchmark scenarios and results
    docs/      Architecture and decision records
