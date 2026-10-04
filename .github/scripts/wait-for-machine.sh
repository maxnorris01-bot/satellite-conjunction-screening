#!/usr/bin/env bash
# Wait for a Fly Machine's run to finish: poll `flyctl machine list --json` until the Machine is
# stopped AND has an exit event from this run (timestamp >= START_MS), or fail after DEADLINE_S.
#
# Why not `flyctl machine wait --wait-timeout 15m`: fly-go clamps each Machines API wait request to
# 60 s (flaps/flaps_machines_wait.go, proxyTimeoutThreshold), and flyctl doesn't retry the
# resulting `deadline_exceeded` (it isn't in isRetryableWaitError's list), so that command gives up
# after 60 s whatever --wait-timeout says. Daily-run 37242110531 failed exactly that way (ADR 0012).
#
# Requiring an exit event from this run, not just state == stopped, guards against reading the
# previous run's `stopped` state in the moment before the start takes effect.
#
# Env: FLY_APP, FLY_MACHINE_ID, START_MS (ms since epoch, taken just before `machine start`).
# Optional: DEADLINE_S (default 900), POLL_INTERVAL_S (default 10). Exit 0 when finished (the exit
# *code* is checked by the workflow's next step), 1 on deadline.
set -euo pipefail

: "${FLY_APP:?}" "${FLY_MACHINE_ID:?}" "${START_MS:?}"
deadline_s=${DEADLINE_S:-900}
interval_s=${POLL_INTERVAL_S:-10}
started_at=$(date +%s)
state=unknown

echo "Waiting up to ${deadline_s}s for machine $FLY_MACHINE_ID to stop (polling every ${interval_s}s)..."
while :; do
  # A failed poll (network blip, API hiccup) is logged and retried, not fatal; only the deadline is.
  if json=$(flyctl machine list -a "$FLY_APP" --json 2>/dev/null); then
    read -r state finished < <(jq -r --arg id "$FLY_MACHINE_ID" --argjson t "$START_MS" '
      [.[] | select(.id == $id)] | first
      | if . == null then "missing false"
        else "\(.state) \([.events[]? | select(.type == "exit" and .timestamp >= $t)] | length > 0)"
        end' <<<"$json")
    if [ "$state" = "stopped" ] && [ "$finished" = "true" ]; then
      echo "Machine $FLY_MACHINE_ID stopped after $(( $(date +%s) - started_at ))s."
      exit 0
    fi
    if [ "$state" = "missing" ]; then
      echo "::warning::Machine $FLY_MACHINE_ID not in flyctl machine list output; retrying."
    fi
  else
    echo "::warning::flyctl machine list failed; retrying."
  fi
  elapsed=$(( $(date +%s) - started_at ))
  if [ "$elapsed" -ge "$deadline_s" ]; then
    echo "::error title=Machine did not stop::Machine $FLY_MACHINE_ID was still '$state' after ${deadline_s}s (a normal run takes about 2 minutes). It may be hung or very slow: check fly logs -a $FLY_APP, and stop it with fly machine stop $FLY_MACHINE_ID before re-running."
    exit 1
  fi
  sleep "$interval_s"
done
