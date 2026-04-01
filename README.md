# MPAC Reference Runtime

This repository contains a Python reference runtime for the Multi-Principal Agent Coordination Protocol (`MPAC`) described in [SPEC.md](./SPEC.md).

## What is implemented

- Common MPAC message envelope and typed payload models
- Session join, leave, heartbeat, and presence tracking
- Intent lifecycle management
- Operation proposal, commit, reject, and supersede flows
- Rule-based conflict detection and reporting
- Basic governance resolution with escalation to an owner or arbiter
- Mock agents that consume and emit MPAC messages
- A runnable end-to-end demo and unit tests

## Run the tests

```bash
python3 -m unittest discover -s tests
```

## Run the demo

```bash
python3 examples/demo_basic.py
```

The demo starts a session, joins two contributor agents and one owner, creates overlapping intents, triggers a conflict, escalates it, and resolves it through a mock owner agent.

## Run the Appendix A scenario tests

```bash
python3 -m unittest discover -s tests
```

This includes five executable tests for the five Appendix A walkthroughs in `SPEC.md`.

## Explore the five spec scenarios in a browser

First export the scenario traces:

```bash
python3 scripts/export_scenarios.py
```

Then serve the repo root as static files:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/frontend/` to browse the scenario explorer. The page shows:

- protocol-fit notes for each scenario
- the full message timeline
- final participants, intents, operations, conflicts, and resolutions

## Run the live playground with real agents

The repository now also includes a separate interactive playground that keeps the static scenario browser intact while adding a real API-backed coordination demo.

Start the local server:

```bash
python3 -m mpac.web.server --port 8000
```

Then open:

- `http://localhost:8000/frontend/` for the original static story demo
- `http://localhost:8000/playground/` for the live interactive playground
- `http://localhost:8000/guided/` for the five step-by-step Appendix A guided scenarios

For the live playground, provide an Anthropic API key in one of these ways:

```bash
export ANTHROPIC_API_KEY=your_key_here
python3 -m mpac.web.server --port 8000
```

Or create a local config file in the repo root:

```bash
cp local_config.example.json local_config.json
```

Then edit `local_config.json` and fill in your key:

```json
{
  "anthropic": {
    "api_key": "your_key_here",
    "model": "claude-sonnet-4-20250514"
  }
}
```

Or paste the key directly into the playground form, which sends it only to your local server process.
