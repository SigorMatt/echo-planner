# echo-planner

A small restocking-planner agent built on the **OpenAI Agents SDK** and exported over
**OTLP/HTTP** with stock OpenInference instrumentation. It exists to produce one
ordinary agent run's telemetry. The spec is in
[`EXPORT-CONTRACT.md`](EXPORT-CONTRACT.md) (contract version 1.2) and
[`BRIEF-Z3.md`](BRIEF-Z3.md).

## What the agent does

The agent gets a list of twelve hardware items, each with an order quantity. It works
through the list in a 25-turn loop. On each odd turn it calls `check_inventory(item)`.
On each even turn it calls `place_order(item, qty)`. On turn 25 it gives a one-sentence
summary and calls no tool. On every turn the Agents SDK resends the full conversation to
the model, as agent frameworks do, so turn *t* carries the *t−1* earlier tool results.
Both tools are local Python functions with fixed data. In recorded mode, a local
OpenAI-compatible stub (`stub_server.py`) plays the model. Its reply at turn *t* depends
only on *t*, where *t* = 1 + the number of tool results in the request. The stub also
fixes the response id, `created`, model name, tool-call ids and token usage per turn, so
every recorded run is identical.

## Pinned packages

| Role | Package | Version |
|---|---|---|
| Framework | `openai-agents` | 0.23.1 |
| Model client (the SDK's own) | `openai` | 3.29.0 |
| Instrumentation (framework) | `openinference-instrumentation-openai-agents` | 2.5.3 |
| Instrumentation (client) | `openinference-instrumentation-openai` | 0.1.65 |
| OpenTelemetry SDK | `opentelemetry-sdk` | 1.45.1 |
| Exporter | `opentelemetry-exporter-otlp-proto-http` | 1.45.1 |

These were the newest releases of each package when this was built (2026-10-12), and
they work together. There was no incompatibility to record. `requirements.lock` holds the
full dependency tree: 59 packages, exact versions and hashes. `make` installs it with
`pip install --no-deps --require-hashes`. It was exported from `uv.lock` (`make lock`) and
supports Python 3.10–3.14 (the instrumentors require `<3.15`).

## Model

- **Recorded run:** `echo-planner-stub`, served by `stub_server.py` at
  `http://127.0.0.1:8765/v1` (fixed port).
- **Real run:** passed as `MODEL=<id>` to `make run-real`. The intended model is
  `gpt-4.1-mini`, served through the OpenAI-compatible gateway the contract owner names.
  The model that was actually used is written to `MANIFEST.json`.

The agent uses the SDK's Chat Completions model (`set_default_openai_api("chat_completions")`)
instead of the Responses API, because the real run goes to an OpenAI-compatible gateway
that may not serve `/responses`.

## Running

```bash
make run                                  # = make run-recorded, telemetry to http://localhost:4318
make run-recorded ENDPOINT=http://host:4318
OPENAI_API_KEY=... OPENAI_BASE_URL=https://gateway.example/v1 make run-real MODEL=<id>
```

The first run creates `.venv/` with `python3` (override with `PYTHON=python3.13`). You do
not need an OTLP endpoint. If none is listening, the SDK logs the export failures and the
run still completes. Each run writes `MANIFEST.json` in the repository root before the
first model call. The copy committed here comes from a recorded run.

`make run-real` reads `OPENAI_API_KEY` and `OPENAI_BASE_URL` from the environment. These
are the `openai` client's own variables, read by `AsyncOpenAI()`. If `OPENAI_BASE_URL` is
unset, the client uses its default, `https://api.openai.com/v1`.

## Telemetry configuration

- The stock `TracerProvider()` gets its resource from the environment:
  `OTEL_SERVICE_NAME=echo-planner`.
- It uses one `BatchSpanProcessor` at defaults wrapping `OTLPSpanExporter()` at defaults
  (protobuf). The exporter sends to `$OTEL_EXPORTER_OTLP_ENDPOINT/v1/traces`, and the
  Makefile sets `OTEL_EXPORTER_OTLP_ENDPOINT=$(ENDPOINT)`.
- Two instrumentors are on in the same process:
  `OpenAIAgentsInstrumentor().instrument()` and `OpenAIInstrumentor().instrument()`. The
  first, at its default `exclusive_processor=True`, replaces the SDK's own trace
  processors. That means nothing is sent to OpenAI's tracing backend.
- On exit the agent calls `provider.shutdown()` to flush.
- **Content capture:** OpenInference records message content on span attributes by
  default. The Makefile still sets these documented variables explicitly, so the caller's
  shell cannot change them:
  `OPENINFERENCE_HIDE_INPUTS=false`, `OPENINFERENCE_HIDE_OUTPUTS=false`,
  `OPENINFERENCE_HIDE_INPUT_MESSAGES=false`, `OPENINFERENCE_HIDE_OUTPUT_MESSAGES=false`,
  `OPENINFERENCE_HIDE_INPUT_TEXT=false`, `OPENINFERENCE_HIDE_OUTPUT_TEXT=false`.

**Observed and left as is:** in later turns the SDK logs `Attributes dict is full.
Dropping the oldest key-value pair…`. This happens because the instrumentor writes one
attribute per field of each resent history message. Past the SDK's default limit of 128
attributes per span, the SDK drops the oldest ones. The limit is left at its default, as
the contract requires.
