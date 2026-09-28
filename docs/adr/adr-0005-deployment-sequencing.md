# ADR 0005: Defer containerization/scheduled deployment past session 1

**Status:** Proposed (Cowork scoping session, 2026-09-27)

## Context

`Applied_AI_Portfolio_Plan.md` names two deployment options: containerize with Docker and host on
AWS Lambda (container-image support) on an EventBridge schedule, or a simpler VPS/Fly.io cron job as
"a faster first pass." Committing to either before the core pipeline is proven risks the same
pattern `Engineering_Standards.md` flags in the Claim Verification retrospective — building out
infrastructure/scope before the thing it's hosting is validated.

## Decision

Session 1 runs the pipeline locally (a plain script/CLI invocation), with no deployment work at all.
Deployment (Fly.io/VPS cron as the faster first pass, per the plan doc, with AWS Lambda + EventBridge
as a possible later step once the pipeline's resource needs — memory, runtime — are known from
real measurements) is explicitly a session-2-or-later decision, made once session 1's timing numbers
(propagation + screening wall-clock time at whatever scope is being run) are in hand.

## Consequences

- No deployment-related tasks belong in session 1's scope or Claude Code's first-session todo list.
- When deployment is picked up, the choice between Fly.io/VPS cron and Lambda+EventBridge should
  reference session 1/2's actual measured runtime and memory footprint, not be guessed upfront.
- The plan doc's other deployment guardrails (thresholds/params in config, step cap per run,
  `send_alert` channel allow-list, kill-switch, structured JSONL run logs) apply once the LLM/alerting
  upgrade is built, not to this MVP core — noted here so they aren't accidentally implemented early
  for a pipeline that doesn't call `send_alert` yet.
