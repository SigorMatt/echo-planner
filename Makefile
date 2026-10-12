# echo-planner — one complete agent run per invocation, telemetry over OTLP/HTTP.
#   make run                          recorded mode (key-free local stub), default endpoint
#   make run ENDPOINT=http://h:p      same, telemetry to another OTLP endpoint
#   make run-recorded                 explicit recorded mode
#   make run-real MODEL=<id>          real model; needs OPENAI_API_KEY (and OPENAI_BASE_URL for a gateway)

ENDPOINT ?= http://localhost:4318
MODEL ?=
PYTHON ?= python3
VENV := .venv

# Stock OpenTelemetry SDK configuration (environment variables only).
export OTEL_SERVICE_NAME := echo-planner
export OTEL_EXPORTER_OTLP_ENDPOINT = $(ENDPOINT)

# OpenInference content capture: content goes on spans; these are the documented
# defaults, stated explicitly so the run does not depend on the caller's shell.
export OPENINFERENCE_HIDE_INPUTS := false
export OPENINFERENCE_HIDE_OUTPUTS := false
export OPENINFERENCE_HIDE_INPUT_MESSAGES := false
export OPENINFERENCE_HIDE_OUTPUT_MESSAGES := false
export OPENINFERENCE_HIDE_INPUT_TEXT := false
export OPENINFERENCE_HIDE_OUTPUT_TEXT := false

.PHONY: run run-recorded run-real install lock clean

run: run-recorded

run-recorded: $(VENV)/.installed
	$(VENV)/bin/python agent.py --mode recorded

run-real: $(VENV)/.installed
	@test -n "$(MODEL)" || { echo "usage: make run-real MODEL=<id>"; exit 2; }
	$(VENV)/bin/python agent.py --mode real --model "$(MODEL)"

install: $(VENV)/.installed

# Full lock of the dependency tree (uv export of uv.lock), installed with --no-deps.
$(VENV)/.installed: requirements.lock
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --quiet --no-deps --require-hashes -r requirements.lock
	touch $@

# Maintainers only: regenerate requirements.lock after editing pyproject.toml.
lock:
	uv lock
	uv export --frozen --no-emit-project --format requirements-txt -o requirements.lock

clean:
	rm -rf $(VENV)
