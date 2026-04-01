"""Local HTTP server for the static story demo and live playground."""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from mpac.live import (
    AnthropicClient,
    AnthropicConfigError,
    CoordinationDemo,
    DemoConfig,
    GuidedScenarioSession,
    create_guided_session,
    list_guided_scenarios,
    load_local_config,
)


ROOT = Path(__file__).resolve().parents[2]
SESSIONS: dict[str, CoordinationDemo] = {}
GUIDED_SESSIONS: dict[str, GuidedScenarioSession] = {}


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._send_json(
                {
                    "ok": True,
                    "anthropic_configured": bool(self._anthropic_api_key()),
                    "default_model": self._anthropic_model(),
                    "playground_url": "/playground/",
                    "guided_url": "/guided/",
                    "stories_url": "/frontend/",
                }
            )
        if parsed.path == "/api/guided/scenarios":
            return self._send_json({"items": list_guided_scenarios()})
        if parsed.path.startswith("/api/guided/session/"):
            session_id = parsed.path.rsplit("/", 1)[-1]
            session = GUIDED_SESSIONS.get(session_id)
            if session is None:
                return self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown guided session: {session_id}")
            return self._send_json(session.to_dict())
        if parsed.path.startswith("/api/session/"):
            session_id = parsed.path.rsplit("/", 1)[-1]
            session = SESSIONS.get(session_id)
            if session is None:
                return self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown session: {session_id}")
            return self._send_json(session.snapshot())
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/session":
            return self._create_session()
        if parsed.path == "/api/guided/session":
            return self._create_guided_session()
        if parsed.path.startswith("/api/guided/session/") and parsed.path.endswith("/next"):
            session_id = parsed.path.split("/")[-2]
            return self._advance_guided_session(session_id)
        if parsed.path.startswith("/api/session/") and parsed.path.endswith("/resolve"):
            session_id = parsed.path.split("/")[-2]
            return self._resolve_session(session_id)
        self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown endpoint: {parsed.path}")

    def _create_session(self) -> None:
        try:
            body = self._read_json_body()
            llm = AnthropicClient(model=body.get("model") or self._anthropic_model(), api_key=self._anthropic_api_key())
            agent_specs = body.get("agents") or DemoConfig().agent_specs
            session = CoordinationDemo(
                llm,
                DemoConfig(
                    model=body.get("model") or self._anthropic_model(),
                    human_name=body.get("human_name") or "Local Operator",
                    agent_specs=agent_specs,
                ),
            )
            result = session.run_round(
                task=body.get("task") or "Coordinate work on a shared artifact.",
                shared_targets=body.get("shared_targets") or [],
            )
            SESSIONS[session.session_id] = session
            self._send_json(result, status=HTTPStatus.CREATED)
        except AnthropicConfigError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover - exercised manually in browser
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _resolve_session(self, session_id: str) -> None:
        session = SESSIONS.get(session_id)
        if session is None:
            return self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown session: {session_id}")
        try:
            body = self._read_json_body()
            result = session.resolve_conflict(
                conflict_id=body["conflict_id"],
                accepted_ids=body.get("accepted_ids") or [],
                rejected_ids=body.get("rejected_ids") or [],
                rationale=body.get("rationale") or "Resolved from the live playground.",
            )
            self._send_json(result)
        except Exception as exc:  # pragma: no cover - exercised manually in browser
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _create_guided_session(self) -> None:
        try:
            body = self._read_json_body()
            llm = None
            if self._anthropic_api_key():
                llm = AnthropicClient(model=body.get("model") or self._anthropic_model(), api_key=self._anthropic_api_key())
            session = create_guided_session(body["scenario_id"], llm=llm)
            GUIDED_SESSIONS[session.session_id] = session
            self._send_json(session.to_dict(), status=HTTPStatus.CREATED)
        except KeyError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except AnthropicConfigError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover - exercised manually in browser
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _advance_guided_session(self, session_id: str) -> None:
        session = GUIDED_SESSIONS.get(session_id)
        if session is None:
            return self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown guided session: {session_id}")
        try:
            self._send_json(session.advance())
        except Exception as exc:  # pragma: no cover - exercised manually in browser
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    def _anthropic_api_key(self) -> str | None:
        config = load_local_config()
        anthropic = config.get("anthropic", {}) if isinstance(config, dict) else {}
        return self.headers.get("X-Anthropic-Api-Key") or anthropic.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")

    def _anthropic_model(self) -> str | None:
        config = load_local_config()
        anthropic = config.get("anthropic", {}) if isinstance(config, dict) else {}
        return self.headers.get("X-Anthropic-Model") or anthropic.get("model") or os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the MPAC static stories and live playground.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Serving MPAC demos on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
