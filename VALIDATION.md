# Validation — bidirectional loop

## Team build adapter (`claudex-team-build`) — 2026-09-11

### Automated suite

47 tests. On Windows, 45 run and pass; the two POSIX executable-bit tests are skipped there and run in CI on Linux and macOS. The 28 earlier tests are unchanged, except that the fake CLI now names its build output per provider (`built_claude.py` / `built_codex.py`).

### Fake CLI only (no model quota)

**Frontend build launch**
- Gemini frontend builds from both hosts, with `accept-edits` and `--sandbox`, and without `--dangerously-skip-permissions` or `--continue`.
- A handoff that carries the plan, baseline, proof command and dependency protocol.
- A Gemini model that must be listed by `agy models`, and effort bounds.
- `--provider` combined with `--builder agy` is refused before any launch.

**Outcomes that never become completion**
- COMPLETE is distinguished from BACKEND_DEPENDENCY (`blocked`) and INCOMPLETE.
- Malformed reports, a missing proof check, evidence-less checks, turn failure, a missing result, a non-zero exit, empty output, a wrong conversation and timeout never become completion. A timeout still records its partial-work snapshot.
- An argv log shows no fallback to Claude or Codex, and a non-frontend chain never invokes `agy`.
- A denied headless action that ends the run, as observed live, is `failed` and names the denied actions.

**Inspection routing**
- Mixed work goes to the provider opposite the primary builder, for both hosts, with delegated and host-direct (`stage`) primaries.
- Gemini-only work goes to the host provider, and an additional explicit review is allowed.
- The backend-dependency sequence: blocked, a wrong conversation refused, a host `stage`, a `--conversation` resume, then a rerouted inspector.

**Handoff safety**
- The one-writer lock.
- An unrelated dirty file, and a stale approval after a contract change, are both refused.
- An index-only `git update-index --chmod=+x` under `core.fileMode=false` is attributed to the right author and reroutes the inspector.
- Both paths of a staged rename are listed.
- Staged index content that differs from the working tree is fingerprinted. A handoff refuses it, a host stage attributes it, and inspection refuses it, text or binary, until the index and working tree agree. Inspection then also receives the staged diff.
- On POSIX, a change between two nonzero executable masks (`0700` → `0710`) is attributed and reroutes the inspector.
- A superseded step is refused as an `--after` position, a `--resume` position or an inspection target, even when the checkout still matches it. A no-change successor therefore cannot be bypassed to reset the budgets.

**Budgets and verification**
- Fix and inspection budgets are job-wide and survive a provider switch; later edits invalidate an older step.
- Claude + Codex cross-inspection counts each pair as one round and refuses the next round once the budget is spent.
- A browser check that never ran is surfaced as a verification gap.
- A non-ASCII result echoed to a cp1252 stream no longer turns a saved, valid run into exit 1. That echo bug was first observed live during this change's plan review.

### Live — 2026-09-11, Windows, Antigravity CLI 1.2.1, `gemini-3.8-flash-high`

**Setup**
- A user-authorized smoke test on a disposable fixture repository, using this worktree's runner.
- The work order was frontend-only (`--unreviewed-spec`): a `greet()` module and an accessible page, checked by a committed `node check.js`.
- The CLI had auto-updated from 1.1.27, the version the adapter was designed against.

| Run | Outcome |
|---|---|
| 1 | `failed`, correctly. Gemini listed an invented path outside the workspace. Headless Antigravity denied it and **ended the turn** with exit 0, an empty report and `denied_actions`. The documentation says soft-denied runs continue; 1.2.1 did not. No files changed, and no other provider launched. |
| 2 | `failed`, correctly, after adding stay-in-checkout guidance and `denied_actions` reporting. The error now named the denial. Gemini still searched a path decoded from the fixture's folder name, because the handoff never gave the absolute checkout path. |
| 3 | `completed`, after the handoff stated the absolute checkout path and marked the plan path reference-only. See details below. |
| 4 | `completed`: fix round 1 through `--resume`. The runner passed `--conversation` with run 3's ID, and Antigravity returned the **same** conversation ID. Only `web/greet.js` changed, and run 3 was marked `superseded_by` run 4. Host checks of the new `farewell()` and the existing `greet()` passed. |

**Run 3 details**
- `accept-edits` with `--sandbox` wrote only `web/greet.js` and `web/index.html`, without any permission bypass.
- The observed model matched the requested one.
- The report was a valid COMPLETE. It honestly marked the proof `NOT_RUN` because the plan forbade commands, and the runner surfaced that in `verification_gaps`.
- The host ran `node check.js` itself and got `ok`.

Each run used about 25,000–60,000 tokens.

**Not exercised live**
- a backend-dependency result;
- a Claude/Codex primary builder in the same chain;
- browser verification of the fixture page;
- a proof command permitted through `permissions.allow`;
- non-Windows platforms;
- the Windows prompt-size ceiling (about 32,000 characters).

Fixture diagnostics stay in the session scratchpad and are not committed.

### Known limitation

Snapshots follow Git's model of a change:
- tracked paths reported by `git diff`, including their Git mode (644 or 755);
- untracked files, including their executable-bit mask.

A permission change that Git does not record, such as `0700` → `0710` on an otherwise unchanged tracked file, is not attributed to anyone. Such a change never reaches the committed deliverable.

## Antigravity research adapter — 2026-09-08

- Automated suite: 28 passing tests, including research from either host, explicit Gemini/fresh-job requirements, rejection of a correctly prefixed model absent from `agy models`, a brief modified during the run, artifacts refused inside the target checkout in research mode, CLI failure, missing/malformed results, omitted workers, incomplete research despite CLI success, timeout handling, and rejection of research as plan approval.
- Live adapter smoke test on Windows with Antigravity CLI 1.1.27 and explicit `gemini-3.8-flash-high`: runner exit 0, structured COMPLETE report, two dispatched workers accounted for, about 55 seconds. Used plan mode and terminal sandboxing without permission bypass. Each worker was limited to two searches; these are smoke-test limits, not production defaults. Findings were based on search summaries with limitations recorded; this was orchestration validation, not a source-accuracy audit.
- Earlier user-run fixtures demonstrated CLI timeout failure, CLI SUCCESS with INCOMPLETE research, and successful bounded synthesis. Forced process-tree termination after both workers recorded a search killed captured local processes; worker transcript hashes stayed unchanged over the 15-second observation window. Immediate cancellation of remote provider requests is unverified. Non-Windows Antigravity cleanup is not live-tested.
- Diagnostics and research reports remain outside the repository; they are not committed fixtures. The runner checks structure and worker accounting; the host still verifies research coverage, worker evidence when needed, and source accuracy.

### Research coverage: live versus fake CLI versus untested — 2026-09-09

Separating what was actually exercised, because the research path mixes runner enforcement with host prose:

- **Live**, once, on Windows with Antigravity CLI 1.1.27 and `gemini-3.8-flash-high`: job launch, plan mode and terminal sandboxing, subagent dispatch, structured COMPLETE parsing, worker accounting, and forced process-tree termination. Not repeated in CI and not covered on macOS or Linux.
- **Fake CLI processes only**, no model quota consumed: schema validation, COMPLETE/INCOMPLETE rules, worker accounting failures, model membership against a stubbed `agy models`, brief hashing at launch and completion, `report.md` written for both outcomes, artifact placement outside the checkout, and timeout handling. These prove the runner's contract, not Antigravity's real behavior.
- **Untested, prose-level host behavior with no automated enforcement**: the Phase 0 sign-off gate on research questions, presenting the complete brief body for approval, retaining and re-checking the approved brief hash, copying the report to `docs/research/`, linking it from the ledger and `PLAN.md`, and the three unavailability choices. The runner cannot observe any of these; a host that skips them still produces a valid run. Stated here rather than implied, because the automated counts above cover none of it.

Development date: 2026-09-06; research coverage entry 2026-09-09. Tests run in disposable fixtures; production repositories were not built or modified by live smoke tests.

## Automated checks

- `python scripts/validate.py`: active skill frontmatter, local references, both provider manifests and shared-runner presence.
- `python -m unittest discover -s tests -v`: **28 passing tests** with fake CLI executables and real temporary Git repositories, without model calls.
- Codex Skill Creator validator: all three active skills.
- Codex Plugin Creator validator: `.codex-plugin/plugin.json`.
- `git diff --check`.

The contract suite covers both host directions, explicit model selection, read-only reviewer argument construction, success/failure parsing, malformed/empty/incomplete output, a failed turn following successful output, session identity on resume, timeout handling, plan hash invalidation, staged/untracked/deleted change coverage, inspection invalidation and preservation of unrelated work during build resumption.

GitHub Actions is configured for Windows, macOS and Linux. Local results establish Windows behavior; cross-platform CI results must be checked on the PR before merge.

## Live model checks

| Check | Result |
|---|---|
| Fable 5.1 reviews a deliberately broken backup plan through the Codex-host route | REVISE; identified deletion-before-read data loss; valid structured output, coverage and session UUID |
| Same Fable session reviews the revised plan | APPROVED with low-priority advice; exact UUID preserved and new plan hash recorded |
| Astra through npm Codex CLI 0.144.5 | Correctly failed, preserving the server error that this model needs a newer CLI |
| Astra through app-bundled Codex CLI 0.153.4 | REVISE; independently identified the seeded data-loss defect; valid structured output |
| Same Astra session reviews the revised plan | APPROVED with zero findings; exact UUID preserved and new plan hash recorded |
| Approval checks on both revised plans | Passed against the actual plan path and current content |
| Fable and Astra separately implement a tiny addition work order | Each created only addition.py; existing acceptance-check file unchanged |
| Host independently runs `python -B check.py` on both implementations | All three acceptance checks passed for each implementation |
| Fresh Astra inspects Fable's code | APPROVED; new untracked addition.py included in the inspected snapshot |
| Fresh Fable inspects Astra's code | APPROVED; new untracked addition.py included in the inspected snapshot |

Fable runs used Claude Code 2.1.261. The Astra test used an explicit CLI executable path rather than changing the user's global installation. The model selection was explicit in both adapters.

Both delegated builders reported that their proof commands were blocked locally: Claude needed approval in headless mode; Codex's Windows sandbox could not access the Python executable. Neither denial was bypassed. The coordinating host ran the proof independently and observed passing results. A completed build turn is not a verified build; the mandatory host proof step resolved these gaps before final inspection.

The fixture checks exercise transport and obvious-defect detection, not comparative model quality. No claim is made that one pairing is better or that an APPROVED response proves exhaustive correctness. A future benchmark should compare defect recall, false positives, proof results, time and usage on the same tasks, including sound plans.

## Limits

- Live review tests were run on Windows. Automated fake-CLI coverage is configured for all three operating systems.
- CLI versions, account access and permission behavior can change; diagnostics identify the selected executable and requested model.
- Codex's shell sandbox does not constrain external MCP side effects; review existing tool configuration as described in the runtime reference. Claude's adapter instead removes non-reading tools and MCP from the reviewer.
- Structured-output validation can reject broken transport and inconsistent verdicts, but cannot prove a model's findings or claimed coverage.
