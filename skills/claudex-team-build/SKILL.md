---
name: claudex-team-build
description: "Opt-in team build: Claude or Codex builds the backend, contracts and integration while Antigravity running Gemini builds the full frontend, then one fresh Claude/Codex session inspects the integrated result. Use for claudex-team-build or an explicitly requested Gemini frontend builder; existing Claudex skills never delegate frontend work on their own."
---

# Claudex Team Build

This skill is an opt-in extension of [Claudex Loop](../claudex-loop/SKILL.md).
- The actual current Claude or Codex conversation remains host and coordinator. Identify it from the runtime, as the shared workflow does.
- Read the shared [build reference](../claudex-loop/references/build.md) and [runtime reference](../claudex-loop/references/runtime.md) before launching anything.
- Resolve the runner from the installed `claudex-loop` skill.
- `claudex-loop`, `codex-build`, `codex-review` and `claudex-route` keep their meanings and never delegate frontend work on their own.

## Roles

| Role | Responsibility |
|---|---|
| Host | Requirements, planning, scope split, sequencing, contracts, findings arbitration, authorization and reporting |
| Primary builder | `primary=claude\|codex`, defaulting to the host: backend, server behavior, business logic, shared contracts and end-to-end integration |
| Frontend builder | Antigravity with an explicit Gemini model: UI components, layout, styling, responsive behavior, accessibility, client state, forms, user-experience validation, API consumption and frontend checks |
| Inspector | One fresh Claude/Codex session chosen from the recorded authorship |

Server validation, authorization enforcement, persistence and server business rules stay with the primary builder. Assign mixed framework files by their actual responsibilities, not by folder or extension.

| Actual implementation | Inspector |
|---|---|
| Codex primary + Gemini frontend | Fresh Claude session |
| Claude primary + Gemini frontend | Fresh Codex session |
| Codex only, no frontend work | Fresh Claude session; Gemini is not launched |
| Claude only, no frontend work | Fresh Codex session; Gemini is not launched |
| Gemini only | Fresh session of the host provider |

The runner derives this routing from the recorded authorship (`inspect --after`):
- If a frontend-only task develops backend work, the primary builder activates and final inspection moves to the provider opposite it.
- If Claude and Codex both author code, each inspects the other's edits (`--provider` in both directions). Never claim a provider independently reviewed its own code.
- Planning or arbitrating does not make the host a code author.
- One inspector is the default. Add another only on explicit request, or propose one for a concrete unresolved concern.

## Tunables

| Argument | Default | Meaning |
|---|---|---|
| `plan` / `log` | shared defaults | The reviewed plan or explicitly authorized standalone work order, and the log. Never silently replace a supplied plan with `PLAN.md` |
| `primary` | host | `claude` or `codex` |
| `frontend_model` | none | Required Gemini ID from `agy models`. If omitted, propose one and ask once |
| `frontend_effort` | CLI default | `low`, `medium` or `high` |
| `builder_model`, `inspector_model`, `*_effort` | CLI configuration | As in the shared workflow |
| `agy_cli`, `codex_cli`, `claude_cli` | PATH | Absolute executable passed as `--cli` |
| `MAX_FIX_ROUNDS` / `MAX_INSPECTION_ROUNDS` | 2 / 2 | Job-wide; passed as `--max-fix-rounds` / `--max-inspection-rounds` |

Echo roles, models, paths and budgets before starting. Existing authorization rules apply unchanged. Enabling a frontend builder does not enable deep research or its research-question gate.

## Plan

Use the shared requirements and plan-review phases when planning is needed; do not restart a settled interview. Before implementation, the plan must state:

- Observable acceptance criteria for the complete feature, and whether the work is frontend-only, non-frontend or mixed.
- Provider roles, frontend scope, backend scope and ownership of each shared file.
- API request/response shapes, pagination, errors, authentication expectations, validation responsibilities and other integration contracts.
- Dependencies between work items and which work can proceed independently.
- Exact proof commands and the affected browser flows to verify.
- Whether Antigravity may run the proof command, through a scoped `permissions.allow` rule. Headless Antigravity ends a run at the first denied action. Without a rule, Gemini reports the proof as `NOT_RUN` and the host runs it.

Resolve shared contracts before dependent work. Routine adjustments needed to satisfy agreed requirements stay within the existing authorization. Consequential new scope, such as changed permissions or a breaking public API, returns to the user. A changed reviewed plan goes back through the shared review and approval rules.

## Execute

Work in an isolated, clean worktree. Every step records a position, and each later step passes `--after` with the previous step's `result.json` (details in the build reference). Always pass the job's latest step, even if it failed; the runner refuses a step that has already been continued.

```text
python RUNNER stage --host HOST --repo PROJECT --plan PLAN --approval APPROVED            # host-direct job start
python RUNNER stage --host HOST --repo PROJECT --plan PLAN --approval APPROVED --after STEP   # after the host's own edits
python RUNNER build --host HOST --builder codex --repo PROJECT --plan PLAN --approval APPROVED --proof "CMD" --after STEP
python RUNNER build --host HOST --builder agy --model GEMINI_ID --repo PROJECT --plan PLAN --approval APPROVED --proof "CMD" --after STEP
python RUNNER inspect --host HOST --repo PROJECT --plan PLAN --after FINAL_STEP
```

- **Non-frontend work** never launches Gemini.
- **One writer at a time:** steps run sequentially.
  - Never edit while a delegated step runs.
  - Hand a shared file over only after the current writer's step is recorded. The next handoff carries the latest state, authorship and agreed contract.
- **`stage --after`** attests every change since the previous step as the host's own. Read its printed `changed_files`, and never stage work you did not write.
- **Parallel work** is optional. Use it only in separate worktrees, when ownership and dependencies permit, and integrate sequentially.

## Backend dependency

Gemini reports a contract mismatch as `BACKEND_DEPENDENCY` (runner status `blocked`). The report gives the affected requirement, actual behavior, needed behavior, proposed adjustment and evidence. The host decides whether the agreed feature needs a backend change or the frontend should use the existing contract. If a backend change is needed:

1. Route it to the primary builder, activating that role if the task was frontend-only.
2. Update and communicate the shared contract, applying plan-review rules if the plan changes.
3. Have the primary builder implement and verify the backend adjustment, and record it as a step.
4. Resume Gemini with `--resume BLOCKED_RESULT --after LATEST_STEP` and the confirmed contract in `--feedback`.
5. Verify the integrated result, then inspect it with the updated routing.

Gemini may continue unrelated frontend work while blocked. Temporary implementation mocks must be marked, listed and replaced before claiming end-to-end completion. Legitimate test mocks stay.

## Failures, fixes and budgets

If Antigravity is unavailable, fails, times out or returns `incomplete`:
- Pause the frontend portion and preserve the current state.
- Report the partial work (the step's `changed_files`) and the actual failure.
- The primary builder may continue independent authorized work.
- The user chooses recovery or a provider change. Never substitute Claude/Codex for the frontend, and never blindly relaunch.

Route frontend findings to Gemini and backend findings to the primary builder; the host coordinates integration findings. Keep the inspector read-only; host-run proof and browser checks supplement it.

Budgets and counting:
- **Fix rounds:** one fix round is one host-declared cycle of accepted findings after an inspection or a failed proof. A cycle may involve both builders; pass the same `--fix-round N` to every builder step in it. Returning a confirmed contract to Gemini does not start a new round.
- **Inspection rounds:** each fresh inspection session counts as one round, except that a Claude + Codex pair on the same state counts as one round together. Failed runs count nothing.
- The runner carries both counters through the chain, so switching builders or handling a dependency cannot reset them. It refuses work past either budget.
- Later edits need a new step and a new inspection. If an inspector or the coordinator takes over implementation, stage those edits and have them inspected independently.
- When budgets are exhausted, report remaining findings, blocked dependencies and unreviewed edits.

## Verify and report

Independently run the agreed proof commands against the integrated state, including a meaningful frontend/backend integration check. Builder reports and `verification_gaps` are advisory.

Frontend completion also requires browser verification of the affected flows by an explicitly assigned actor with browser access. Cover the relevant loading, empty, error and responsive states, plus accessibility basics, and record the flows and results. Without browser access, record the limitation and do not claim full frontend verification unless the user accepts the gap.

Report:
- roles and authorship;
- changed scope;
- proof and browser results;
- the inspected snapshot;
- findings and dispositions;
- round usage;
- deviations and unresolved limitations.

Commit, push, installation and publication follow the existing authorization.
