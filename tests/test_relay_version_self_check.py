"""v0.2.25 — relay startup logs its mpac-mcp version + warns on every
chat turn if the on-disk version has drifted from the in-memory one.

Catches the "I upgraded mpac-mcp via pip but the running relay still
serves the old prompt" trap — Python module cache means a running
relay keeps its in-memory _SYSTEM_PROMPT until the process is
restarted, so an `pip install --upgrade` mid-session is invisible
until the user notices the agent's reply still uses the old wording.

These tests lock the helper API and the once-per-process sticky
behavior so a future refactor doesn't accidentally make the warning
spam every turn or stop firing entirely.
"""
import logging
import re

import mpac_mcp.relay as relay_mod


def test_startup_version_captured_at_module_load():
    # Module-level constant must be a non-empty version string captured
    # when the relay process started. "?" sentinel only appears when
    # importlib.metadata can't find the package — running our own tests
    # against the source tree should always succeed.
    assert isinstance(relay_mod._STARTUP_MPAC_MCP_VERSION, str)
    assert relay_mod._STARTUP_MPAC_MCP_VERSION
    assert relay_mod._STARTUP_MPAC_MCP_VERSION != "?"
    # Should look like a SemVer-ish string.
    assert re.match(r"^\d+\.\d+\.\d+", relay_mod._STARTUP_MPAC_MCP_VERSION)


def test_warn_is_silent_when_disk_matches_startup(caplog, monkeypatch):
    # Reset the sticky flag so this test runs in isolation regardless of
    # ordering; production code has its own once-per-process guard.
    monkeypatch.setattr(relay_mod, "_UPGRADE_WARNED", False)
    with caplog.at_level(logging.WARNING, logger="mpac.relay"):
        relay_mod._warn_if_mpac_mcp_upgraded_mid_session()
    # In tests the on-disk version equals the startup version, so the
    # warning MUST stay silent — otherwise we'd spam every chat turn.
    assert not any(
        "upgraded mid-relay" in r.message for r in caplog.records
    )


def test_warn_fires_once_when_disk_drifts_from_startup(caplog, monkeypatch):
    monkeypatch.setattr(relay_mod, "_UPGRADE_WARNED", False)
    monkeypatch.setattr(
        relay_mod, "_read_mpac_mcp_version_from_disk",
        lambda: "9.9.9",  # simulate user upgraded mid-session
    )
    with caplog.at_level(logging.WARNING, logger="mpac.relay"):
        relay_mod._warn_if_mpac_mcp_upgraded_mid_session()
        relay_mod._warn_if_mpac_mcp_upgraded_mid_session()
        relay_mod._warn_if_mpac_mcp_upgraded_mid_session()
    # Sticky: fires exactly once even if called repeatedly. Otherwise
    # every chat turn would re-warn and turn the relay log into noise.
    matches = [
        r for r in caplog.records if "upgraded mid-relay" in r.message
    ]
    assert len(matches) == 1
    # The warning text MUST tell the user the concrete remediation —
    # if a future copy edit drops "Restart this relay" or the version
    # numbers, this assertion catches it.
    msg = matches[0].message
    assert "Restart this relay" in msg
    assert "9.9.9" in msg
    assert relay_mod._STARTUP_MPAC_MCP_VERSION in msg


def test_warn_silent_when_disk_lookup_fails(caplog, monkeypatch):
    # `?` is the sentinel _read_mpac_mcp_version_from_disk returns when
    # importlib.metadata can't find the package. Treat as "can't tell"
    # → don't warn, don't burn the sticky flag (so a real upgrade later
    # still fires).
    monkeypatch.setattr(relay_mod, "_UPGRADE_WARNED", False)
    monkeypatch.setattr(
        relay_mod, "_read_mpac_mcp_version_from_disk", lambda: "?",
    )
    with caplog.at_level(logging.WARNING, logger="mpac.relay"):
        relay_mod._warn_if_mpac_mcp_upgraded_mid_session()
    assert not any(
        "upgraded mid-relay" in r.message for r in caplog.records
    )
    assert relay_mod._UPGRADE_WARNED is False


def test_startup_banner_logs_version_and_path(caplog):
    with caplog.at_level(logging.INFO, logger="mpac.relay"):
        relay_mod._log_startup_version_banner()
    banners = [
        r for r in caplog.records
        if "mpac-mcp version:" in r.message
    ]
    assert len(banners) == 1
    msg = banners[0].message
    assert relay_mod._STARTUP_MPAC_MCP_VERSION in msg
    # User must learn the remediation pattern from the banner alone,
    # not just from the warning when it's already too late.
    assert "restart this" in msg.lower() or "restart this process" in msg.lower()
