"""Standalone event recorder for MPAC test sessions.

Drop-in observability — designed so the entire ``mpac_event_recorder/``
directory can be deleted at any time and the system keeps running.

How it stays decoupled
----------------------
The web app and relay each have ONE call at startup that's wrapped in a
``try: ... except ImportError: pass``::

    try:
        import mpac_event_recorder
        mpac_event_recorder.install()
    except ImportError:
        pass

If this package is missing, the import fails silently and the call sites
behave exactly like they did before this module existed. If it's present
but ``MPAC_EVENT_LOG`` is unset, ``install()`` returns early and nothing
is patched, so it's a no-op at runtime too.

When enabled (env var ``MPAC_EVENT_LOG=/path/to/file.jsonl``), it:

  * Wraps :func:`api.mpac_bridge.process_envelope` to record every MPAC
    envelope flowing through the coordinator (the protocol-level event
    bus). One JSON line per envelope.
  * Adds a :class:`logging.Handler` to the ``mpac`` logger family so any
    ``log.info()`` / ``log.warning()`` calls in the existing code show up
    in the same JSONL stream.
  * Wraps the relay's ``handle_chat`` so every ``claude -p`` subprocess
    spawn / exit / orphan-cleanup is recorded (the relay runs in its own
    process, so this only fires when ``install()`` is called inside that
    process — see ``mpac_event_recorder.relay`` for the relay-side hook).

Each line in the output JSONL has::

    {
      "ts": "2026-04-28T20:14:03.123456+00:00",
      "kind": "envelope" | "log" | "relay_subprocess",
      ...kind-specific fields...
    }

Analyse with ``jq``::

    jq 'select(.kind == "envelope" and .message_type == "CONFLICT_REPORT")' \\
        /tmp/session.jsonl

Removing the recorder
---------------------
``rm -rf mpac_event_recorder/`` — that's it. The try-imports in
``web-app/api/main.py`` and ``mpac-mcp/src/mpac_mcp/relay.py`` will
swallow the ``ImportError`` and the system goes back to its previous
behaviour.
"""
from __future__ import annotations

from .recorder import (  # noqa: F401
    install,
    install_relay,
    is_active,
    record_event,
    shutdown,
)

__all__ = [
    "install",
    "install_relay",
    "is_active",
    "record_event",
    "shutdown",
]
