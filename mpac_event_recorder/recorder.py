"""Core JSONL writer + install hooks.

Designed for *appendonly* JSONL output, one event per line, ordered by
arrival time. We don't try to be a full observability platform — this is
a research-grade session recorder. For production-scale logging, swap in
structlog + Vector + Loki later (the JSONL format is a strict subset of
what those tools want, so the migration is essentially a config change).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


_LOG_PATH_ENV = "MPAC_EVENT_LOG"
_LOG_LEVEL_ENV = "MPAC_EVENT_LOG_LEVEL"
_LOGGER_PREFIX = "mpac"


# ── Module-level state ─────────────────────────────────────────────────
#
# All mutable state lives here. We keep it private so callers go through
# the helpers below, which makes thread-safety + idempotency easy to
# reason about.

_lock = threading.Lock()
_fp = None  # file handle, opened lazily by _open_writer()
_active = False
_installed_web = False
_installed_relay = False
_role: Optional[str] = None  # "web" or "relay" — surfaces in every event


def is_active() -> bool:
    """True iff a writer is currently open. Used by the patches below to
    skip work when recording is disabled (e.g. env var unset)."""
    return _active


def _open_writer(path: str) -> None:
    """Open the JSONL file (line-buffered). Creates parent dirs as needed."""
    global _fp, _active
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    # Line-buffered + append mode = each event lands on disk immediately,
    # so a crash never truncates the most recent record.
    _fp = open(path, "a", buffering=1, encoding="utf-8")
    _active = True


def shutdown() -> None:
    """Close the writer. Mostly used by tests; production processes leave
    the file open until exit (kernel will flush on close)."""
    global _fp, _active, _installed_web, _installed_relay
    with _lock:
        if _fp is not None:
            try:
                _fp.flush()
                _fp.close()
            except Exception:
                pass
        _fp = None
        _active = False
        _installed_web = False
        _installed_relay = False


def record_event(kind: str, **fields: Any) -> None:
    """Append one event to the JSONL file. Safe to call from any thread.

    No-op if the recorder isn't active. Failures (disk full, etc.) are
    swallowed — observability must NOT take down the system it observes.
    """
    if not _active:
        return
    record: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "monotonic": time.monotonic(),
        "role": _role,
        "kind": kind,
    }
    record.update(fields)
    try:
        line = json.dumps(record, default=_json_default, ensure_ascii=False)
    except Exception as e:
        # Fall back to repr-encoded payload — better than dropping the event
        # silently. We still want to know SOMETHING happened.
        line = json.dumps({
            "ts": record["ts"],
            "kind": "encoding_error",
            "original_kind": kind,
            "error": f"{type(e).__name__}: {e}",
        })
    with _lock:
        if _fp is None:
            return
        try:
            _fp.write(line + "\n")
        except Exception:
            pass


def _json_default(obj: Any) -> Any:
    """JSON fallback for things that don't natively serialize.

    Envelopes are dicts of primitives most of the time, but the
    coordinator occasionally surfaces dataclasses (Scope, Intent, ...) or
    enums in nested fields. Cast them to a stable string form so the line
    still parses.
    """
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        try:
            return obj.to_dict()
        except Exception:
            pass
    if hasattr(obj, "value"):  # enums
        return obj.value
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return repr(obj)


# ── Install hooks ──────────────────────────────────────────────────────


def install(role: str = "web") -> bool:
    """Wire up the web-app side. Idempotent + safe to call before the
    web framework imports the wrapped modules.

    Returns True iff recording is now active. The caller doesn't actually
    need to check — the recorder simply does nothing when inactive.
    """
    global _role, _installed_web
    path = os.environ.get(_LOG_PATH_ENV, "").strip()
    if not path:
        # Recorder is shipped but disabled — hands-off mode.
        return False

    with _lock:
        if _installed_web:
            return _active
        if not _active:
            _role = role
            _open_writer(path)
        _installed_web = True

    _install_logging_handler()
    _install_envelope_hook()
    record_event(
        "recorder_started",
        pid=os.getpid(),
        python=sys.version.split()[0],
        path=path,
    )
    return True


def install_relay() -> bool:
    """Wire up the mpac-mcp relay side. Same idempotency rules as
    :func:`install`. Hooks the subprocess spawn / exit / cleanup
    lifecycle in ``mpac_mcp.relay.handle_chat``.
    """
    global _role, _installed_relay
    path = os.environ.get(_LOG_PATH_ENV, "").strip()
    if not path:
        return False

    with _lock:
        if _installed_relay:
            return _active
        if not _active:
            _role = "relay"
            _open_writer(path)
        _installed_relay = True

    _install_logging_handler()
    _install_relay_hook()
    record_event(
        "recorder_started",
        pid=os.getpid(),
        python=sys.version.split()[0],
        path=path,
    )
    return True


# ── Logging handler ────────────────────────────────────────────────────
#
# Catches every existing log.info / log.warning call under the ``mpac``
# logger family. We attach to the ``mpac`` logger (not root) to avoid
# capturing uvicorn / sqlalchemy / httpx noise — that's hundreds of
# unrelated messages per minute. If the user wants those too they can
# raise the level via MPAC_EVENT_LOG_LEVEL=DEBUG.

_handler_attached = False


class _JSONLLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if not _active:
            return
        try:
            msg = record.getMessage()
        except Exception:
            msg = record.msg
        record_event(
            "log",
            level=record.levelname,
            logger=record.name,
            message=msg,
            module=record.module,
            func=record.funcName,
            line=record.lineno,
        )


def _install_logging_handler() -> None:
    global _handler_attached
    if _handler_attached:
        return
    handler = _JSONLLogHandler()
    level_name = os.environ.get(_LOG_LEVEL_ENV, "INFO").upper()
    handler.setLevel(getattr(logging, level_name, logging.INFO))
    logging.getLogger(_LOGGER_PREFIX).addHandler(handler)
    # propagate=True is fine — handler runs in addition to whatever else
    # the app already configured.
    _handler_attached = True


# ── Envelope-stream hook ───────────────────────────────────────────────
#
# Wraps web-app/api/mpac_bridge.process_envelope so every MPAC envelope
# fed through the coordinator gets recorded along with the responses the
# coordinator emits in return. This is the highest-signal source: if the
# UI did or did not see a CONFLICT_REPORT, that fact is right here.

_envelope_hook_installed = False


def _install_envelope_hook() -> None:
    global _envelope_hook_installed
    if _envelope_hook_installed:
        return
    try:
        from api import mpac_bridge as _bridge
    except ImportError:
        # Web-app not on sys.path — caller is probably the relay process.
        return

    original_process = _bridge.process_envelope
    original_coord_process = None

    async def wrapped_process_envelope(session, envelope, sender_principal_id):
        # Snapshot the coordinator's process_message to capture responses.
        # We re-bind per-call so a fresh Coordinator instance is picked up
        # automatically (no need to walk session.coordinator.__class__).
        nonlocal original_coord_process
        coord = session.coordinator
        if original_coord_process is None or getattr(
            coord.process_message, "__mpac_recorder_wrapped__", False,
        ) is False:
            original_coord_process = coord.process_message

            def wrapped_coord_process(env_in):
                responses = original_coord_process(env_in)
                try:
                    record_event(
                        "envelope",
                        direction="inbound",
                        sender=env_in.get("sender", {}).get("principal_id"),
                        message_type=env_in.get("message_type"),
                        message_id=env_in.get("message_id"),
                        payload=env_in.get("payload"),
                    )
                    for resp in responses or []:
                        record_event(
                            "envelope",
                            direction="coordinator_response",
                            in_reply_to=env_in.get("message_id"),
                            message_type=resp.get("message_type"),
                            message_id=resp.get("message_id"),
                            recipient=(
                                resp.get("recipients")
                                or resp.get("recipient")
                            ),
                            payload=resp.get("payload"),
                        )
                except Exception:
                    pass
                return responses

            wrapped_coord_process.__mpac_recorder_wrapped__ = True
            coord.process_message = wrapped_coord_process

        record_event(
            "process_envelope_call",
            sender=sender_principal_id,
            message_type=envelope.get("message_type"),
            message_id=envelope.get("message_id"),
            project_id=getattr(session, "project_id", None),
        )
        return await original_process(session, envelope, sender_principal_id)

    _bridge.process_envelope = wrapped_process_envelope
    # Also patch any modules that already `from api.mpac_bridge import
    # process_envelope`-d at import time. They hold a stale reference to
    # the unwrapped function so the wrapper never fires when they call
    # it. Walk ALL of sys.modules and rebind anywhere the original is —
    # not just api.routes.*, because api.main itself imports
    # process_envelope at module load (before this bootstrap runs) and
    # uses it from its WS handlers. Verified 2026-04-28: filtering to
    # api.routes.* missed api.main.process_envelope and the recorder
    # captured zero envelope events in production until this fix.
    for mod_name, mod in list(sys.modules.items()):
        if mod_name == "api.mpac_bridge":
            continue
        if getattr(mod, "process_envelope", None) is original_process:
            mod.process_envelope = wrapped_process_envelope

    _envelope_hook_installed = True


# ── Relay subprocess hook ──────────────────────────────────────────────
#
# Wraps mpac_mcp.relay.handle_chat so we capture: when a chat is dispatched
# to claude -p, what the exit code was, what stdout/stderr looked like,
# and whether the orphan-intent cleanup endpoint had to fire.

_relay_hook_installed = False


def _install_relay_hook() -> None:
    global _relay_hook_installed
    if _relay_hook_installed:
        return
    try:
        from mpac_mcp import relay as _relay
    except ImportError:
        return

    original_handle = _relay.handle_chat
    original_cleanup = getattr(_relay, "_withdraw_orphan_intents", None)

    async def wrapped_handle_chat(ctx, message):
        record_event(
            "relay_subprocess",
            event="dispatch",
            project_id=ctx.project_id,
            message_len=len(message),
            message_preview=(message[:200] + "…") if len(message) > 200 else message,
        )
        start = time.monotonic()
        reply = await original_handle(ctx, message)
        record_event(
            "relay_subprocess",
            event="reply",
            project_id=ctx.project_id,
            duration_sec=round(time.monotonic() - start, 3),
            reply_preview=(reply[:300] + "…") if len(reply) > 300 else reply,
            looks_like_error=reply.startswith("[relay]"),
        )
        return reply

    _relay.handle_chat = wrapped_handle_chat

    if original_cleanup is not None:
        async def wrapped_cleanup(ctx, reason):
            record_event(
                "relay_subprocess",
                event="orphan_cleanup_call",
                project_id=ctx.project_id,
                reason=reason,
            )
            withdrawn = await original_cleanup(ctx, reason)
            record_event(
                "relay_subprocess",
                event="orphan_cleanup_result",
                project_id=ctx.project_id,
                reason=reason,
                withdrawn_intent_ids=list(withdrawn),
            )
            return withdrawn

        _relay._withdraw_orphan_intents = wrapped_cleanup

    _relay_hook_installed = True
