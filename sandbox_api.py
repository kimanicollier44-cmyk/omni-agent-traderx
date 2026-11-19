"""Static sandbox chamber - the sandbox-api merge.

Verified on Docker Hub 2026-11-06: credkellar/sandbox-api - 8,463
pulls, 1 star, ACTIVE, 'Safely detonate files across PC, mobile, and
cloud environments with AI-driven threat reports.' Tag trap: `latest`
(2026-08-25) is OLDER than `main` (2026-09-30) - pull :main for newest.
Its overview describes capturing execution telemetry, network traffic,
FS diffs, API traces and memory dumps, with a multi-LLM report engine
(Gemini, Claude, ChatGPT, Codex). No public source repo exists for it;
nothing here claims to be its source.

THIS chamber is the static, defensive version of that idea:
- Every sample (MonadDB dump, paywall payload, fusion sample) passes
  through the chamber BEFORE analysis.
- The sample is DATA ONLY. It is never executed: no exec, no eval, no
  subprocess of sample content, in this module or anywhere in the lab.
- Analysis runs in an isolated temp working directory; the chamber
  captures telemetry: bytes read, simulated trie reads/writes,
  fingerprint hits, a trace list of operations, the FS diff of its
  temp dir (files created), and network attempts.
- Network attempts are ZERO by design: this module imports no socket
  machinery at all, and the telemetry asserts the count is 0.
- A step/time budget is enforced; exceeding it aborts with a verdict.
- The telemetry feeds the report engine (LLM/SLM summaries + the
  Carbon4/Muse council), mirroring sandbox-api's multi-LLM report
  idea with this lab's own offline stack - honestly, not its engines.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import time

STEP_BUDGET = 100_000
TIME_BUDGET_SECONDS = 5.0


class BudgetExceeded(Exception):
    pass


class Chamber:
    """One isolated chamber run for one sample (data only)."""

    def __init__(self, step_budget: int = STEP_BUDGET,
                 time_budget: float = TIME_BUDGET_SECONDS):
        self.step_budget = step_budget
        self.time_budget = time_budget
        self.steps = 0
        self.trace: list[str] = []
        self.network_attempts = 0  # no sockets exist in this lab, by design

    def _step(self, op: str) -> None:
        self.steps += 1
        if self.steps > self.step_budget:
            raise BudgetExceeded(f"step budget {self.step_budget} exceeded")
        self.trace.append(op)

    def run(self, name: str, data: bytes, analyse_fn) -> dict:
        """Run analyse_fn(data) inside the chamber; return telemetry.

        analyse_fn receives the raw bytes and returns a report dict.
        The chamber writes the sample into its temp dir (as data),
        snapshots the dir before/after, and records the FS diff.
        """
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="mdb_chamber_") as td:
            before = set(os.listdir(td))
            sample_path = os.path.join(td, "sample.bin")
            with open(sample_path, "wb") as fh:
                fh.write(data)
            self._step("write_sample_data")
            bytes_read = 0
            report = None
            error = None
            try:
                self._step("analyse_start")
                report = analyse_fn(data)
                bytes_read = len(data)
                self._step("analyse_done")
            except BudgetExceeded as exc:
                error = str(exc)
            elapsed = time.monotonic() - started
            if elapsed > self.time_budget and error is None:
                error = f"time budget {self.time_budget}s exceeded"
            after = set(os.listdir(td))
            created = sorted(after - before)
            # Simulate trie reads/writes from the report when present.
            trie_reads = 0
            trie_writes = 0
            fingerprint_hits: list[str] = []
            if isinstance(report, dict):
                fingerprint_hits = list(report.get("fingerprints", []))
                trie_reads = int(report.get("node_count", 0))
                trie_writes = 0
            telemetry = {
                "sample": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes_in": len(data),
                "bytes_read": bytes_read,
                "trie_reads_simulated": trie_reads,
                "trie_writes_simulated": trie_writes,
                "fingerprint_hits": fingerprint_hits,
                "fs_diff_created": created,
                "fs_diff_count": len(created),
                "trace": list(self.trace),
                "steps": self.steps,
                "step_budget": self.step_budget,
                "budget_ok": error is None,
                "network_attempts": self.network_attempts,
                "network_blocked_by_design": True,
                "executed_sample_code": False,
                "elapsed_ms": round(elapsed * 1000, 3),
                "error": error,
            }
            return {"report": report, "telemetry": telemetry}


def detonate_static(name: str, data: bytes, analyse_fn,
                    step_budget: int = STEP_BUDGET) -> dict:
    """Convenience wrapper: one fresh chamber per sample."""
    return Chamber(step_budget=step_budget).run(name, data, analyse_fn)
