# Pet project briefs — six agents, six telemetry shapes

Each brief is given to its implementer together with `EXPORT-CONTRACT.md`
and nothing else. A brief says what the agent does and which packages
instrument it. It never says what the telemetry should look like.

Implementers pin exact versions of every package they name; the versions
below are "current at time of writing" and are theirs to confirm.

---
## Z3 — `echo-planner`: a long history-resending loop under the OpenAI Agents SDK

**Framework and instrumentation.** The OpenAI Agents SDK, instrumented by
`openinference-instrumentation-openai-agents`, **plus** the SDK's own
OpenAI client instrumented by `openinference-instrumentation-openai` — two
instrumentors in one process, both left on.

**What it does.** A planning agent runs a 25-turn loop: each turn it calls
one of two tools (`check_inventory(item)` or `place_order(item, qty)`), and
the framework resends the full conversation history to the model on every
turn, as agent frameworks do. The stub model's reply at turn *t* depends
only on *t*, so the loop is deterministic and always 25 turns.

**Scenario, fixed.** Alternate `check_inventory` and `place_order`; the last
turn is a final answer with no tool call.

**Why this shape.** History echo at scale (turn *t* carries *t−1* prior tool
results), and two instrumentors claiming the same underlying call.

---

## What every brief has in common

- `make run-recorded` is deterministic; `make run-real` is run once against
  a real model with the endpoint we give.
- The implementer does not know what consumes the traces and does not look.
- Where a brief asks for something the contract forbids (Z4's one manual
  span, Z5's missing shutdown), the brief wins, exactly as far as it says.
