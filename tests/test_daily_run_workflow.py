"""The daily-run workflow's wait and exit-code logic, against a fake `flyctl` (ADR 0012).

Runs the real `.github/scripts/wait-for-machine.sh` and the real "Check exit code" step script
(read out of `.github/workflows/daily-run.yml`), with a fake `flyctl` on PATH that returns a
scripted sequence of `machine list --json` responses, one per call (the last one repeats).
No Fly account, network or GitHub runner involved.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WAIT_SCRIPT = REPO / ".github" / "scripts" / "wait-for-machine.sh"
WORKFLOW = REPO / ".github" / "workflows" / "daily-run.yml"
MACHINE = "m1"
START_MS = 1_000_000

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("jq")), reason="needs bash and jq"
)


def machine(state: str, events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return [{"id": MACHINE, "state": state, "events": events or []}]


def exit_event(ts: int, code: int | None = None) -> dict[str, Any]:
    # Fly omits exit_code when it's 0 (omitempty), so code=None models a successful exit.
    exit_ev: dict[str, Any] = {"requested_stop": False}
    if code is not None:
        exit_ev["exit_code"] = code
    return {"type": "exit", "timestamp": ts, "request": {"exit_event": exit_ev}}


OLD_EXIT = exit_event(START_MS - 60_000, 0)  # the previous run's exit, before this run started


def fake_flyctl(tmp_path: Path, responses: list[Any], logs: str = "") -> dict[str, str]:
    """Install a fake flyctl; `responses` items are JSON-able, or the string "FAIL" for an error."""
    d = tmp_path / "fake"
    (d / "bin").mkdir(parents=True)
    for i, r in enumerate(responses):
        (d / f"resp_{i}").write_text("FAIL" if r == "FAIL" else json.dumps(r))
    (d / "logs").write_text(logs)
    (d / "bin" / "flyctl").write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            d={d}
            if [ "$1 $2" = "machine list" ]; then
              n=$(cat "$d/count" 2>/dev/null || echo 0)
              echo $((n + 1)) > "$d/count"
              last={len(responses) - 1}
              [ "$n" -gt "$last" ] && n=$last
              body=$(cat "$d/resp_$n")
              [ "$body" = FAIL ] && {{ echo "Error: api hiccup" >&2; exit 1; }}
              echo "$body"
            elif [ "$1" = logs ]; then
              cat "$d/logs"
            else
              echo "unexpected flyctl call: $*" >&2; exit 2
            fi
            """
        )
    )
    (d / "bin" / "flyctl").chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{d / 'bin'}:{os.environ['PATH']}",
        "FLY_APP": "app",
        "FLY_MACHINE_ID": MACHINE,
        "START_MS": str(START_MS),
        "POLL_INTERVAL_S": "0",
    }


def run_wait(env: dict[str, str], deadline_s: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(WAIT_SCRIPT)],
        env={**env, "DEADLINE_S": str(deadline_s)},
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_exit_code_step(env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["run"]["steps"]
    (script,) = [s["run"] for s in steps if s.get("name") == "Check exit code"]
    (cwd / "start_ms").write_text(str(START_MS))
    return subprocess.run(
        ["bash", "-c", script], env=env, cwd=cwd, capture_output=True, text=True, timeout=60
    )


def test_still_running_then_stops_ok(tmp_path: Path) -> None:
    env = fake_flyctl(
        tmp_path,
        [
            machine("stopped", [OLD_EXIT]),  # before the start takes effect: must not count
            machine("started", [OLD_EXIT]),
            machine("started", [OLD_EXIT]),
            machine("stopped", [OLD_EXIT, exit_event(START_MS + 110_000)]),
        ],
    )
    r = run_wait(env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "stopped after" in r.stdout
    assert (tmp_path / "fake" / "count").read_text().strip() == "4"
    step = run_exit_code_step(env, tmp_path)
    assert step.returncode == 0, step.stdout + step.stderr
    assert "Machine exit code: 0" in step.stdout


def test_stopped_with_exit_1_finishes_wait_then_fails_exit_check(tmp_path: Path) -> None:
    env = fake_flyctl(
        tmp_path,
        [machine("started"), machine("stopped", [exit_event(START_MS + 5_000, 1)])],
        logs='app[m1] {"event": "failed", "error": "RuntimeError(\'boom\')"}\n',
    )
    r = run_wait(env)
    assert r.returncode == 0, r.stdout + r.stderr
    step = run_exit_code_step(env, tmp_path)
    assert step.returncode == 1
    assert "Machine exit code: 1" in step.stdout
    assert "title=Run failed" in step.stdout


def test_exit_1_from_celestrak_403_is_reported_as_cooldown(tmp_path: Path) -> None:
    env = fake_flyctl(
        tmp_path,
        [machine("stopped", [exit_event(START_MS + 5_000, 1)])],
        logs='app[m1] {"event": "failed", "error": "HTTPStatusError(403 Forbidden)"}\n',
    )
    assert run_wait(env).returncode == 0
    step = run_exit_code_step(env, tmp_path)
    assert step.returncode == 1
    assert "CelesTrak cooldown (403)" in step.stdout


def test_never_stops_fails_at_deadline_with_clear_message(tmp_path: Path) -> None:
    env = fake_flyctl(tmp_path, [machine("started", [OLD_EXIT])])
    r = run_wait(env, deadline_s=2)
    assert r.returncode == 1
    assert "title=Machine did not stop" in r.stdout
    assert "was still 'started' after 2s" in r.stdout


def test_stale_stop_from_previous_run_is_not_mistaken_for_this_run(tmp_path: Path) -> None:
    env = fake_flyctl(tmp_path, [machine("stopped", [OLD_EXIT])])
    r = run_wait(env, deadline_s=2)
    assert r.returncode == 1
    assert "was still 'stopped'" in r.stdout


def test_transient_flyctl_failure_is_retried(tmp_path: Path) -> None:
    env = fake_flyctl(tmp_path, ["FAIL", machine("stopped", [exit_event(START_MS + 5_000)])])
    r = run_wait(env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "flyctl machine list failed; retrying" in r.stdout


def test_fly_token_reaches_only_the_steps_that_call_flyctl() -> None:
    job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["run"]
    assert "FLY_API_TOKEN" not in job.get("env", {})
    calls_flyctl = {
        s["name"]
        for s in job["steps"]
        if "run" in s and ("flyctl " in s["run"] or "wait-for-machine.sh" in s["run"])
    }
    has_token = {
        s.get("name", s.get("uses")) for s in job["steps"] if "FLY_API_TOKEN" in s.get("env", {})
    }
    assert calls_flyctl == {"Start the Machine", "Wait for it to stop", "Check exit code"}
    assert has_token == calls_flyctl


def test_checkout_is_pinned_and_drops_credentials() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["run"]["steps"]
    (checkout,) = [s for s in steps if s.get("uses", "").startswith("actions/checkout@")]
    ref = checkout["uses"].split("@", 1)[1]
    assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)
    assert checkout["with"]["persist-credentials"] is False
