# ADR 0002: A LangGraph version of the agent, for comparison

- Status: accepted
- Date: 2026-11-09

## Context

ADR 0001 chose an explicit agent loop over a framework, for transparency and testability.
That choice deserved evidence, not just an argument. LangGraph is the agent framework from
the LangChain ecosystem: an agent is a graph of nodes, state is saved by a checkpointer,
and a run can pause for a human with `interrupt()`.

## Decision

Build a second implementation, `maia/agent/langgraph_agent.py`, with the same interface
(`send`, `resolve`) and run both through the same benchmark.

To compare the orchestration and nothing else, both use the same model client
(`ChatModel`, through LiteLLM), the same system prompt, the same tool registry and the same
safety code. LangChain's own model classes are not used: they would change the model
client too, and the benchmark could not meter tokens and cost the same way.

| | Explicit loop | LangGraph |
|---|---|---|
| Control flow | a `for` loop | nodes and conditional edges |
| Confirmation gate | pending calls kept on the conversation | `interrupt()` in a `confirm` node |
| Conversation state | a `Conversation` object | a checkpointer, keyed by session id |
| Step limit | `MAX_STEPS` in the loop | a step counter in the state |

## Consequences

- The benchmark can compare `explicit` and `langgraph` on the same model and scenarios.
- Behaviour must match: `tests/test_langgraph_agent.py` mirrors the main agent tests, and
  the runner test runs both agents.
- A LangGraph pitfall to remember: on resume, an interrupted node runs again from the top.
  The `confirm` node therefore calls `interrupt()` before anything with side effects, and
  tools that change nothing run in a separate `tools` node so they are never run twice.
- The checkpointer is in memory, as the explicit agent's store is. A production version
  would use LangGraph's Postgres checkpointer so conversations survive restarts.
