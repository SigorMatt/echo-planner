"""Key-free, OpenAI-compatible stub for `make run-recorded`.

Serves POST /v1/chat/completions. The reply at turn t depends only on t, where
t = 1 + the number of tool results already in the request's history. Turns
1..24 alternate check_inventory / place_order over a fixed item list; turn 25
is a final answer with no tool call. Every field of the reply (id, created,
model, tool-call ids, usage) is fixed per turn.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}/v1"
MODEL = "echo-planner-stub"
TOTAL_TURNS = 25
CREATED = 1760000000

ITEMS = [
    ("bolts", 200),
    ("nuts", 200),
    ("washers", 150),
    ("hinges", 40),
    ("brackets", 60),
    ("screws", 500),
    ("anchors", 80),
    ("rivets", 300),
    ("clamps", 25),
    ("springs", 90),
    ("gaskets", 120),
    ("pulleys", 10),
]

FINAL_ANSWER = (
    "Plan complete: checked inventory and placed one restock order for each of "
    + ", ".join(item for item, _ in ITEMS)
    + "."
)


def reply_for_turn(t: int) -> dict:
    """The full chat.completion body for turn t (1-based)."""
    if t >= TOTAL_TURNS:
        message = {"role": "assistant", "content": FINAL_ANSWER}
        finish_reason = "stop"
    else:
        item, qty = ITEMS[(t - 1) // 2]
        if t % 2 == 1:
            name, args = "check_inventory", {"item": item}
        else:
            name, args = "place_order", {"item": item, "qty": qty}
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_turn_{t:02d}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args, sort_keys=True)},
                }
            ],
        }
        finish_reason = "tool_calls"
    prompt_tokens = 200 + 60 * (t - 1)
    completion_tokens = 20
    return {
        "id": f"chatcmpl-stub-{t:02d}",
        "object": "chat.completion",
        "created": CREATED,
        "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send(404, {"error": {"message": f"no route {self.path}"}})
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if body.get("stream"):
            self._send(400, {"error": {"message": "the stub does not stream"}})
            return
        t = 1 + sum(1 for m in body.get("messages", []) if m.get("role") == "tool")
        self._send(200, reply_for_turn(t))

    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        pass


def start_in_thread() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    print(f"stub listening on {BASE_URL}", file=sys.stderr)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
