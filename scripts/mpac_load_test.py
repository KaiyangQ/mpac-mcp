"""MPAC load test — in-process coordinator, N simulated participants.

Tests the protocol + analyzer under concurrent load WITHOUT real WebSockets,
HTTP, auth, DB, or Claude API. This isolates the bottleneck we actually
care about (coordinator + analyzer scaling) from stack overhead.

Run::

    PYTHONPATH="mpac-package/src" \\
      .venv/bin/python scripts/mpac_load_test.py \\
      --agents 100 \\
      --project-files 200 \\
      --announces-per-agent 5

What it simulates
-----------------
1. A synthetic project of ``--project-files`` .py files with a realistic
   cross-import graph (each file imports 2-4 others, ~30% form small
   chains → forcing the reverse-dep scanner to work).
2. ``--agents`` participants all joining one session.
3. Each agent runs a work loop for ``--announces-per-agent`` iterations:
   pick 1-4 files, build a scope with impact (mirrors what web-app does),
   announce, sleep briefly, withdraw. Files are picked with bias so
   realistic overlaps happen — the 100-agent-on-same-session stress case.

What it measures
----------------
* Per-announce latency: ``announce_intent`` wall-clock, broken into
  analyzer cost vs coordinator cost.
* Aggregate throughput: announces/sec across all agents.
* Coordinator memory footprint (RSS snapshot at peak).
* Conflict detection rate (sanity check: higher N ⇒ more conflicts).

What it does NOT test
---------------------
* FastAPI / uvicorn / WebSocket overhead. If this test passes, stack
  overhead is probably the next bottleneck; run the HTTP smoke separately.
* SQLite contention. Web-app fetches files from DB per announce; here we
  pass the pre-built sources dict in memory.
* Claude API latency. A real agent adds seconds of thinking per announce.
"""
from __future__ import annotations

import argparse
import os
import random
import resource
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Make the local mpac-package importable without install
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, "mpac-package", "src"))

from mpac_protocol.analysis import scan_reverse_deps  # noqa: E402
from mpac_protocol.core.coordinator import SessionCoordinator  # noqa: E402
from mpac_protocol.core.models import Scope  # noqa: E402
from mpac_protocol.core.participant import Participant  # noqa: E402


# ─── Synthetic project ─────────────────────────────────────────────


def build_synthetic_project(n_files: int, seed: int = 42) -> Dict[str, str]:
    """Generate ``n_files`` fake .py files with a realistic import graph.

    Each file imports 2-4 others (picked from earlier files to avoid
    cycles). About 30% are "hubs" that many later files import from —
    these are the files where editing would ripple widely, which is the
    stress case for the reverse-dep scanner.
    """
    rng = random.Random(seed)
    paths = [f"pkg/module_{i:04d}.py" for i in range(n_files)]
    files: Dict[str, str] = {}

    # Hubs: first 30% of files become commonly-imported
    hub_cutoff = max(5, n_files * 3 // 10)
    hubs = paths[:hub_cutoff]

    for i, p in enumerate(paths):
        imports: List[str] = []
        candidates = paths[:i]  # only import earlier modules
        if not candidates:
            body = f"def helper_{i}():\n    return {i}\n"
        else:
            # 60% chance to import a hub
            n_imports = rng.randint(1, min(4, len(candidates)))
            for _ in range(n_imports):
                if hubs and rng.random() < 0.6:
                    target = rng.choice(hubs)
                else:
                    target = rng.choice(candidates)
                if target not in imports:
                    imports.append(target)
            body_lines = []
            for t in imports:
                mod = t[:-3].replace("/", ".")
                body_lines.append(f"from {mod} import helper_{int(t.split('_')[1].split('.')[0])}")
            body_lines.append("")
            body_lines.append(f"def helper_{i}():")
            body_lines.append(f"    return {i}")
            body = "\n".join(body_lines) + "\n"
        files[p] = body

    # Add a pkg/__init__.py so the package structure is valid.
    files["pkg/__init__.py"] = ""
    return files


# ─── One agent loop ────────────────────────────────────────────────


@dataclass
class AgentStats:
    name: str
    announce_latencies_ms: List[float] = field(default_factory=list)
    analyzer_latencies_ms: List[float] = field(default_factory=list)
    coordinator_latencies_ms: List[float] = field(default_factory=list)
    conflicts_seen: int = 0


def run_agent(
    agent_idx: int,
    coord: SessionCoordinator,
    project_files: Dict[str, str],
    file_paths: List[str],
    n_announces: int,
    rng: random.Random,
) -> AgentStats:
    """Simulate one agent's work loop.

    Announces and withdraws ``n_announces`` times, picking 1-4 random files
    each round. File selection is biased toward the first 20% of the corpus
    so agents overlap — realistic "everyone's editing the hot modules"
    pattern that stresses both scope_overlap and dep_conflict paths.
    """
    principal_id = f"agent_{agent_idx:04d}"
    display = principal_id
    session_id = coord.session_id

    # Join session
    participant = Participant(
        principal_id=principal_id,
        principal_type="agent",
        display_name=display,
        roles=["contributor"],
        capabilities=["intent.broadcast", "op.commit"],
    )
    coord.process_message(participant.hello(session_id))

    stats = AgentStats(name=principal_id)
    hot_zone = max(1, len(file_paths) // 5)  # first 20% — hot

    for round_idx in range(n_announces):
        # Pick 1-4 files, 60% from hot zone
        n_files = rng.randint(1, 4)
        picks = []
        for _ in range(n_files):
            if rng.random() < 0.6:
                picks.append(rng.choice(file_paths[:hot_zone]))
            else:
                picks.append(rng.choice(file_paths))
        picks = list(dict.fromkeys(picks))  # dedupe preserving order

        intent_id = f"intent-{principal_id}-{round_idx}"

        # ── Time the analyzer separately from the coordinator ──
        t0 = time.perf_counter()
        impact = scan_reverse_deps(picks, project_files)
        t1 = time.perf_counter()

        scope = Scope(
            kind="file_set",
            resources=picks,
            extensions={"impact": impact} if impact else None,
        )

        envelope = participant.announce_intent(
            session_id=session_id,
            intent_id=intent_id,
            objective="load-test",
            scope=scope,
        )
        responses = coord.process_message(envelope)
        t2 = time.perf_counter()

        analyzer_ms = (t1 - t0) * 1000
        coordinator_ms = (t2 - t1) * 1000
        total_ms = (t2 - t0) * 1000
        stats.analyzer_latencies_ms.append(analyzer_ms)
        stats.coordinator_latencies_ms.append(coordinator_ms)
        stats.announce_latencies_ms.append(total_ms)

        # Did the coordinator emit any CONFLICT_REPORT for me?
        for r in responses:
            if r.get("message_type") == "CONFLICT_REPORT":
                stats.conflicts_seen += 1

        # Withdraw (keeps the live-intent set bounded)
        coord.process_message(
            participant.withdraw_intent(
                session_id=session_id,
                intent_id=intent_id,
                reason="round_done",
            )
        )

    return stats


# ─── Driver ────────────────────────────────────────────────────────


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _rss_mb() -> float:
    """Current process resident memory in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux reports kilobytes.
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=10)
    ap.add_argument("--project-files", type=int, default=200)
    ap.add_argument("--announces-per-agent", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--interleave", action="store_true",
                    help="Interleave rounds across agents (pseudo-concurrent) "
                         "instead of one-agent-at-a-time. Closer to real load.")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    print(f"\nMPAC load test")
    print(f"  agents:              {args.agents}")
    print(f"  project files:       {args.project_files}")
    print(f"  announces per agent: {args.announces_per_agent}")
    print(f"  interleave:          {args.interleave}")
    print(f"  total announces:     {args.agents * args.announces_per_agent}")

    print("\n[1/3] Building synthetic project…")
    t0 = time.perf_counter()
    project_files = build_synthetic_project(args.project_files, seed=args.seed)
    file_paths = [p for p in project_files if p != "pkg/__init__.py"]
    print(f"      {len(project_files)} files in {(time.perf_counter() - t0)*1000:.0f} ms")

    print("\n[2/3] Initializing coordinator + participants…")
    t0 = time.perf_counter()
    coord = SessionCoordinator("load-test-session", security_profile="open")
    rss_start = _rss_mb()
    print(f"      coord up in {(time.perf_counter() - t0)*1000:.1f} ms; "
          f"RSS baseline {rss_start:.1f} MB")

    print("\n[3/3] Running work loops…")
    t_start = time.perf_counter()

    all_stats: List[AgentStats] = []
    if args.interleave:
        # Round-robin: all agents do round 1, then round 2, etc. Closer to
        # concurrent load (the coordinator's live-intent set grows).
        # We still process serially (single-threaded Python), but the LIVE
        # state profile matches many agents acting at once.
        participants: List[Participant] = []
        for i in range(args.agents):
            pid = f"agent_{i:04d}"
            p = Participant(
                principal_id=pid,
                principal_type="agent",
                display_name=pid,
                roles=["contributor"],
                capabilities=["intent.broadcast", "op.commit"],
            )
            coord.process_message(p.hello(coord.session_id))
            participants.append(p)
            all_stats.append(AgentStats(name=pid))

        hot_zone = max(1, len(file_paths) // 5)
        for round_idx in range(args.announces_per_agent):
            # Pass 1: all agents announce
            live_intents: List[Tuple[int, str]] = []
            for i, p in enumerate(participants):
                n_files = rng.randint(1, 4)
                picks = []
                for _ in range(n_files):
                    if rng.random() < 0.6:
                        picks.append(rng.choice(file_paths[:hot_zone]))
                    else:
                        picks.append(rng.choice(file_paths))
                picks = list(dict.fromkeys(picks))
                intent_id = f"intent-{p.principal_id}-{round_idx}"

                t0 = time.perf_counter()
                impact = scan_reverse_deps(picks, project_files)
                t1 = time.perf_counter()
                scope = Scope(
                    kind="file_set",
                    resources=picks,
                    extensions={"impact": impact} if impact else None,
                )
                env = p.announce_intent(
                    session_id=coord.session_id,
                    intent_id=intent_id,
                    objective="load-test",
                    scope=scope,
                )
                responses = coord.process_message(env)
                t2 = time.perf_counter()

                s = all_stats[i]
                s.analyzer_latencies_ms.append((t1 - t0) * 1000)
                s.coordinator_latencies_ms.append((t2 - t1) * 1000)
                s.announce_latencies_ms.append((t2 - t0) * 1000)
                for r in responses:
                    if r.get("message_type") == "CONFLICT_REPORT":
                        s.conflicts_seen += 1
                live_intents.append((i, intent_id))

            # Pass 2: all agents withdraw
            for i, intent_id in live_intents:
                coord.process_message(
                    participants[i].withdraw_intent(
                        session_id=coord.session_id,
                        intent_id=intent_id,
                        reason="round_done",
                    )
                )
    else:
        for i in range(args.agents):
            s = run_agent(
                i, coord, project_files, file_paths,
                args.announces_per_agent, rng,
            )
            all_stats.append(s)

    t_end = time.perf_counter()
    rss_peak = _rss_mb()
    wall_s = t_end - t_start

    # Aggregate
    all_announce = [x for s in all_stats for x in s.announce_latencies_ms]
    all_analyzer = [x for s in all_stats for x in s.analyzer_latencies_ms]
    all_coord = [x for s in all_stats for x in s.coordinator_latencies_ms]
    total_conflicts = sum(s.conflicts_seen for s in all_stats)
    throughput = len(all_announce) / wall_s if wall_s > 0 else 0

    def fmt(values: List[float]) -> str:
        if not values:
            return "-"
        return (f"mean={statistics.mean(values):.1f}  "
                f"P50={percentile(values, 0.50):.1f}  "
                f"P95={percentile(values, 0.95):.1f}  "
                f"P99={percentile(values, 0.99):.1f}  "
                f"max={max(values):.1f} ms")

    print(f"\n─── Results ─────────────────────────────────────────")
    print(f"wall time:           {wall_s:.2f} s")
    print(f"announces completed: {len(all_announce)}")
    print(f"throughput:          {throughput:.1f} announces/s")
    print(f"conflicts reported:  {total_conflicts}")
    print(f"coordinator live intents at end: {len(coord.intents)}")
    print(f"RSS baseline → peak: {rss_start:.1f} → {rss_peak:.1f} MB")
    print(f"")
    print(f"announce total:      {fmt(all_announce)}")
    print(f"  analyzer portion:  {fmt(all_analyzer)}")
    print(f"  coordinator portion: {fmt(all_coord)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
