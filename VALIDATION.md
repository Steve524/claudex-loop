# Validation — bidirectional loop

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
