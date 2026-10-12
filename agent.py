"""echo-planner: a 25-turn restocking planner on the OpenAI Agents SDK.

Telemetry: stock OpenTelemetry SDK (BatchSpanProcessor + OTLP/HTTP exporter, all
defaults, configured from OTEL_* environment variables) with two stock
OpenInference instrumentors, both on.
"""

import argparse
import asyncio
import json
import os
import platform
from datetime import datetime, timezone
from importlib.metadata import version

from openai import AsyncOpenAI
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agents import (
    Agent,
    ModelSettings,
    Runner,
    function_tool,
    set_default_openai_api,
    set_default_openai_client,
)

import stub_server

INSTRUMENTATION = ["openinference-instrumentation-openai-agents", "openinference-instrumentation-openai"]
EXPORTER = "opentelemetry-exporter-otlp-proto-http"

STOCK = {
    "bolts": 35,
    "nuts": 120,
    "washers": 0,
    "hinges": 12,
    "brackets": 7,
    "screws": 410,
    "anchors": 3,
    "rivets": 95,
    "clamps": 0,
    "springs": 44,
    "gaskets": 18,
    "pulleys": 2,
}
ORDERS: list[dict] = []

INSTRUCTIONS = (
    "You are a restocking planner for a hardware store. For each item in the user's "
    "list, in order: first call check_inventory(item), then call place_order(item, qty) "
    "with the quantity given in the list. Call exactly one tool per turn. After the last "
    "order, reply with a one-sentence summary and do not call any tool."
)
TASK = "Restock these items (item: order quantity): " + "; ".join(
    f"{item}: {qty}" for item, qty in stub_server.ITEMS
)


@function_tool
def check_inventory(item: str) -> str:
    """Return the number of units of an item currently on hand."""
    return json.dumps({"item": item, "on_hand": STOCK.get(item, 0)})


@function_tool
def place_order(item: str, qty: int) -> str:
    """Place a restock order for qty units of an item."""
    order = {"order_id": f"PO-{len(ORDERS) + 1:04d}", "item": item, "qty": qty, "status": "placed"}
    ORDERS.append(order)
    return json.dumps(order)


def write_manifest(mode: str, model: str, base_url: str, started_at: str) -> None:
    manifest = {
        "contract_version": "1.2",
        "framework": "openai-agents",
        "framework_version": version("openai-agents"),
        "instrumentation": [f"{pkg}=={version(pkg)}" for pkg in INSTRUMENTATION],
        "sdk": {
            "opentelemetry-sdk": version("opentelemetry-sdk"),
            "exporter": f"{EXPORTER}=={version(EXPORTER)}",
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model": model,
        "base_url": base_url,
        "mode": mode,
        "endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        "started_at": started_at,
    }
    with open("MANIFEST.json", "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


async def run(mode: str, model: str) -> None:
    if mode == "recorded":
        stub = stub_server.start_in_thread()
        client = AsyncOpenAI(base_url=stub_server.BASE_URL, api_key="stub-no-key")
    else:
        client = AsyncOpenAI()  # OPENAI_API_KEY / OPENAI_BASE_URL from the environment
    set_default_openai_client(client)
    set_default_openai_api("chat_completions")

    agent = Agent(
        name="echo-planner",
        instructions=INSTRUCTIONS,
        model=model,
        tools=[check_inventory, place_order],
        model_settings=ModelSettings(parallel_tool_calls=False),
    )

    started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    write_manifest(mode, model, str(client.base_url), started_at)
    try:
        result = await Runner.run(agent, TASK, max_turns=stub_server.TOTAL_TURNS)
        print(result.final_output)
    finally:
        if mode == "recorded":
            stub.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["recorded", "real"], default="recorded")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    if args.mode == "recorded":
        model = stub_server.MODEL
    elif args.model:
        model = args.model
    else:
        parser.error("--model is required in real mode (make run-real MODEL=<id>)")

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    OpenAIAgentsInstrumentor().instrument(tracer_provider=provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    try:
        asyncio.run(run(args.mode, model))
    finally:
        provider.shutdown()


if __name__ == "__main__":
    main()
