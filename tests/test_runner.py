"""Contract tests use real subprocesses and disposable Git repositories, no model calls."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runner", ROOT / "skills/claudex-loop/scripts/runner.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
SESSION = "12345678-1234-4567-8123-123456789abc"
GOOD = {"verdict": "APPROVED", "summary": "The supplied acceptance criteria are consistent.",
        "findings": [], "coverage": ["docs/custom plan.md"], "limitations": []}

FAKE_CLI = r'''
import json, os, pathlib, sys, time
if os.environ.get('FAKE_LOG'):
    with open(os.environ['FAKE_LOG'], 'a', encoding='utf-8') as log:
        log.write(json.dumps(sys.argv[1:]) + '\n')
if '--version' in sys.argv:
    print('fake-cli 1.0')
    sys.exit(0)
if 'models' in sys.argv:
    print('gemini-test Gemini Test')
    sys.exit(0)
prompt = sys.stdin.read()
case = os.environ.get('FAKE_CASE', 'ok')
if case == 'timeout':
    time.sleep(30)
if case == 'exit':
    print('Authentication failed', file=sys.stderr)
    sys.exit(7)
if case == 'empty':
    sys.exit(0)
if case == 'mutate_plan':
    pathlib.Path(os.environ['FAKE_PLAN']).write_text('Changed after launch')
if case == 'mutate_brief':
    pathlib.Path(os.environ['FAKE_BRIEF']).write_text('Brief changed after launch')
if case == 'mutate_code':
    pathlib.Path('new.py').write_text('changed during inspection')
if case == 'build':
    pathlib.Path('built_codex.py' if 'exec' in sys.argv else 'built_claude.py').write_text('print(42)\n')
session = '12345678-1234-4567-8123-123456789abc'
if case == 'wrong_session':
    session = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
review = {'verdict':'APPROVED', 'summary':'Inspected supplied plan.',
          'findings':[], 'coverage':['custom plan.md'], 'limitations':[]}
if case == 'unicode':
    review['summary'] = 'Checked the plan ' + chr(0x2192) + ' consistent.'
if case == 'revise':
    review.update(verdict='REVISE', findings=[{'id':'R1','severity':'high','path':'plan',
                  'evidence':'Deletion before successful copy loses the only copy.',
                  'fix':'Verify the new copy before removing the old one.'}])
if case == 'blocked':
    review.update(verdict='BLOCKED', coverage=[], limitations=['Required schema unavailable.'])
if case == 'malformed':
    review = {'verdict':'APPROVED'}
if 'accept-edits' in sys.argv:
    if case == 'fe_timeout':
        pathlib.Path('partial.js').write_text('// partial\n')
        time.sleep(30)
    pathlib.Path(os.environ.get('FAKE_UI_FILE', 'ui.js')).write_text(os.environ.get('FAKE_UI', 'render();\n'))
    if os.environ.get('FAKE_UI_MODE'):
        os.chmod(os.environ.get('FAKE_UI_FILE', 'ui.js'), int(os.environ['FAKE_UI_MODE'], 8))
    if '--conversation' in sys.argv:
        session = sys.argv[sys.argv.index('--conversation') + 1]
    if case == 'wrong_session':
        session = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    value = {'status':'COMPLETE', 'summary':'Built the table view.', 'changed_files':['ui.js'],
             'checks':[{'name':'npm test', 'kind':'proof', 'status':'PASSED', 'evidence':'3 passed'}],
             'dependencies':[], 'mocks':[], 'limitations':[]}
    if case == 'fe_dependency':
        value.update(status='BACKEND_DEPENDENCY', mocks=['ui.js: TEMP total count'], dependencies=[{
            'requirement':'Show the total row count', 'actual':'GET /items returns only the page',
            'needed':'A total field in the response', 'proposal':'Add total to GET /items',
            'evidence':'api.py returns a bare list'}])
    if case == 'fe_incomplete':
        value.update(status='INCOMPLETE', limitations=['Styling unfinished.'])
    if case == 'fe_mock':
        value['mocks'] = ['ui.js: TEMP data']
    if case == 'fe_gap':
        value['checks'].append({'name':'table flow', 'kind':'browser', 'status':'NOT_RUN',
                                'evidence':'No browser tool in the headless session.'})
    if case == 'fe_noproof':
        value['checks'] = []
    if case == 'fe_noevidence':
        value['checks'][0]['evidence'] = ''
    if case == 'malformed':
        value = {'status':'COMPLETE'}
    print(json.dumps({'event':'init','conversation_id':session,'init':{
        'model':sys.argv[sys.argv.index('--model') + 1], 'tools':['write_to_file'],
        'permission_mode':'accept-edits'}}))
    result = {'conversation_id':session, 'status':'ERROR' if case == 'turn_failed' else 'SUCCESS',
              'structured_output':value}
    if case == 'fe_denied':  # Antigravity 1.2.1 ends a headless turn at the first denied action
        result = {'conversation_id':session, 'status':'SUCCESS', 'response':'',
                  'denied_actions':[{'action':'read_file', 'display_name':'ListDir'}]}
    if case != 'incomplete':
        print(json.dumps({'event':'result','result':result}))
elif '--print-timeout' in sys.argv:
    value = {'status':'COMPLETE', 'report':'Findings with sources.',
             'sources':['https://example.org/source'], 'limitations':[], 'workers':[]}
    if case == 'research_incomplete':
        value.update(status='INCOMPLETE', sources=[], limitations=['Source unavailable.'])
    if case == 'malformed':
        value = {'status':'COMPLETE'}
    print(json.dumps({'event':'init','conversation_id':session,'init':{'model':'gemini-test'}}))
    if case == 'missing_worker':
        print(json.dumps({'event':'step_update','step_update':{'subagent_info':{
            'subagents':[{'conversation_id':'worker-1'}]}}}))
    if case != 'incomplete':
        print(json.dumps({'event':'result','result':{'conversation_id':session,
            'status':'ERROR' if case == 'turn_failed' else 'SUCCESS',
            'structured_output':value}}))
elif 'exec' in sys.argv:
    output = pathlib.Path(sys.argv[sys.argv.index('-o')+1])
    output.write_text('Built; proof passed.' if case == 'build' else json.dumps(review))
    print(json.dumps({'type':'thread.started', 'thread_id':session}))
    if case == 'turn_failed':
        print(json.dumps({'type':'turn.failed', 'error':{'message':'quota'}}))
    elif case != 'incomplete':
        print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':5}}))
else:
    value = {'type':'result','subtype':'success','is_error':False,'session_id':session,
             'structured_output':review, 'result':'Built; proof passed.',
             'modelUsage':{'claude-test':{'inputTokens':10}},'usage':{'input_tokens':10}}
    if case == 'turn_failed':
        value.update(subtype='error_during_execution',is_error=True)
    print(json.dumps([{'type':'system','subtype':'init'}, value] if case == 'array' else value))
'''


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="claudex-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.plan = self.root / "custom plan.md"
        self.plan.write_text("# Work order\nKeep the original until the copy is verified.\n", encoding="utf-8")
        self.brief = self.root / "research brief.md"
        self.brief.write_text("# Brief\nWhat do teams get wrong about restores?\n", encoding="utf-8")
        self.artifacts = self.root / "runs"
        self.log = self.root / "calls.log"
        self.cli = self.root / "fake_cli.py"
        self.cli.write_text(FAKE_CLI)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "existing.py").write_text("original\n")
        (self.repo / "delete.py").write_text("delete me\n")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, stderr=subprocess.PIPE).decode()

    def invoke(self, host="claude", mode="review", case="ok", extra=(), env=None):
        args = [mode, "--host", host, "--repo", str(self.repo), "--plan", str(self.plan),
                "--artifacts", str(self.artifacts), *extra]
        old = set(self.artifacts.glob("*/result.json")) if self.artifacts.exists() else set()
        output, error = io.StringIO(), io.StringIO()
        with patch.object(runner, "cli_prefix", return_value=[sys.executable, str(self.cli)]), \
             patch.dict(os.environ, {"FAKE_CASE": case, "FAKE_PLAN": str(self.plan),
                                     "FAKE_BRIEF": str(self.brief), "FAKE_LOG": str(self.log),
                                     **(env or {})}), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = runner.main(args)
        new = set(self.artifacts.glob("*/result.json")) - old if self.artifacts.exists() else set()
        path = next(iter(new)) if new else None
        return code, json.loads(path.read_text()) if path else None, path, error.getvalue()

    def frontend(self, host="claude", case="fe_ok", extra=(), env=None):
        return self.invoke(host, "build", case, ("--builder", "agy", "--model", "gemini-test",
                                                 "--unreviewed-spec", "--proof", "npm test", *extra), env)

    def build(self, builder, host="claude", extra=()):
        return self.invoke(host, "build", "build", ("--builder", builder, "--unreviewed-spec",
                                                    "--proof", "python -m unittest", *extra))

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def reset(self):
        self.git("reset", "--hard", "-q")
        self.git("clean", "-fdq")

    def test_host_role_defaults_and_builder_override(self):
        self.assertEqual(runner.resolve_roles("claude")["reviewer"], "codex")
        self.assertEqual(runner.resolve_roles("codex")["reviewer"], "claude")
        roles = runner.resolve_roles("codex", builder="claude")
        self.assertEqual((roles["planner"], roles["builder"], roles["inspector"]), ("codex", "claude", "codex"))
        with self.assertRaises(runner.RunError):
            runner.resolve_roles("codex", "codex")

    def test_research_success_and_incomplete_from_both_hosts(self):
        extra = ('--brief', str(self.plan), '--model', 'gemini-test')
        for host in runner.PROVIDERS:
            code, record, path, _ = self.invoke(host, mode='research', extra=extra)
            self.assertEqual(code, 0, record)
            self.assertEqual(record['provider'], 'agy')
            self.assertTrue((path.parent / 'report.md').is_file())
            with self.assertRaises(runner.RunError):
                runner.check_approval(record, self.plan, self.repo)
        code, record, path, _ = self.invoke(mode='research', case='research_incomplete', extra=extra)
        self.assertEqual(code, 1)
        self.assertEqual(record['status'], 'incomplete')
        self.assertEqual(record['exit_code'], 0)
        self.assertTrue((path.parent / 'report.md').is_file())

    def test_research_rejects_failed_missing_malformed_and_unaccounted_results(self):
        for case in ('exit', 'empty', 'malformed', 'turn_failed', 'incomplete', 'missing_worker', 'timeout'):
            with self.subTest(case=case):
                code, record, _, _ = self.invoke(mode='research', case=case,
                    extra=('--brief', str(self.plan), '--model', 'gemini-test', '--timeout', '1'))
                self.assertEqual(code, 1)
                self.assertEqual(record['status'], 'failed')

    def test_research_requires_gemini_and_fresh_job_without_plan(self):
        for extra in ((), ('--model', 'claude-test'),
                      ('--model', 'gemini-test', '--resume', 'previous.json')):
            code, record, _, _ = self.invoke(mode='research', extra=('--brief', str(self.plan), *extra))
            self.assertEqual(code, 1)
            self.assertIsNone(record)
        code, record, _, _ = self.invoke(mode='research', extra=(
            '--brief', str(self.plan), '--model', 'gemini-test', '--plan', 'absent.md'))
        self.assertEqual(code, 0, record)

    def test_research_rejects_model_absent_from_agy_models(self):
        code, record, path, _ = self.invoke(mode='research', extra=(
            '--brief', str(self.brief), '--model', 'gemini-absent'))
        self.assertEqual(code, 1)
        self.assertEqual(record['status'], 'failed')
        self.assertIn('gemini-absent', record['error'])
        self.assertIn('models.txt', record['error'])
        self.assertTrue((path.parent / 'models.txt').is_file())

    def test_research_brief_changed_during_run_fails(self):
        code, record, _, _ = self.invoke(mode='research', case='mutate_brief', extra=(
            '--brief', str(self.brief), '--model', 'gemini-test'))
        self.assertEqual(code, 1)
        self.assertEqual(record['status'], 'failed')
        self.assertIn('brief', record['error'].lower())

    def test_both_review_adapters_complete_and_bind_custom_plan(self):
        for host in ("claude", "codex"):
            with self.subTest(host=host):
                code, record, path, _ = self.invoke(host)
                self.assertEqual(code, 0, record)
                self.assertEqual(record["session_id"], SESSION)
                self.assertEqual(record["plan"], str(self.plan))
                self.assertEqual(record["plan_sha256"], runner.digest(self.plan.read_bytes()))
                self.assertIn(str(self.plan), (path.parent / "prompt.txt").read_text())
                self.assertEqual(record["response"]["verdict"], "APPROVED")

    def test_unpinned_and_explicit_model_selection(self):
        for provider in runner.PROVIDERS:
            args = runner.command(provider, "review", self.root)
            self.assertNotIn("--model", args)
            self.assertNotIn("-m", args)
            pinned = runner.command(provider, "review", self.root, "chosen-model", "high")
            self.assertIn("chosen-model", pinned)

    def test_claude_exposes_only_read_tools_and_no_mcp(self):
        args = runner.command("claude", "review", self.root)
        self.assertEqual(args[args.index("--tools")+1], "Read,Glob,Grep")
        self.assertIn("--safe-mode", args)
        self.assertIn("--strict-mcp-config", args)
        self.assertEqual(args[args.index("--permission-mode")+1], "dontAsk")

    def test_codex_resume_keeps_read_only_and_explicit_session(self):
        args = runner.command("codex", "review", self.root, session=SESSION)
        self.assertEqual(args[:3], ["exec", "resume", SESSION])
        self.assertIn('sandbox_mode="read-only"', args)
        self.assertNotIn("-s", args)
        self.assertNotIn("--last", args)

    def test_failures_never_approve_and_keep_diagnostics(self):
        for host in ("claude", "codex"):
            for case in ("exit", "empty", "malformed", "turn_failed"):
                with self.subTest(host=host, case=case):
                    code, record, path, _ = self.invoke(host, case=case)
                    self.assertEqual(code, 1)
                    self.assertEqual(record["status"], "failed")
                    self.assertTrue((path.parent / "stderr.txt").exists())
                    if case == "exit":
                        self.assertIn("Authentication failed", (path.parent / "stderr.txt").read_text())

    def test_missing_codex_completion_is_failure(self):
        code, record, _, _ = self.invoke(case="incomplete")
        self.assertEqual(code, 1)
        self.assertEqual(record["status"], "failed")

    def test_claude_array_envelope(self):
        code, record, _, _ = self.invoke("codex", case="array")
        self.assertEqual(code, 0)
        self.assertEqual(record["observed_models"], ["claude-test"])

    def test_revise_and_blocked_are_completed_but_not_approval(self):
        for case in ("revise", "blocked"):
            code, record, _, _ = self.invoke(case=case)
            self.assertEqual(code, 0)
            with self.assertRaises(runner.RunError):
                runner.check_approval(record, self.plan, self.repo)

    def test_empty_findings_allowed_but_contradictory_approval_rejected(self):
        runner.validate_review(copy.deepcopy(GOOD))
        value = copy.deepcopy(GOOD)
        value["findings"] = [{"id":"1", "severity":"high", "path":"plan", "evidence":"data loss", "fix":"retain copy"}]
        with self.assertRaises(runner.RunError):
            runner.validate_review(value)

    def test_changed_plan_invalidates_approval(self):
        _, record, _, _ = self.invoke()
        runner.check_approval(record, self.plan, self.repo)
        self.plan.write_text("Different requirements")
        with self.assertRaises(runner.RunError):
            runner.check_approval(record, self.plan, self.repo)

    def test_changed_plan_during_review_fails(self):
        code, record, _, _ = self.invoke(case="mutate_plan")
        self.assertEqual(code, 1)
        self.assertIn("changed during", record["error"])

    def test_resume_revised_plan_same_session(self):
        _, _, previous, _ = self.invoke(case="revise")
        self.plan.write_text("New revision")
        code, record, _, _ = self.invoke(extra=("--resume", str(previous)))
        self.assertEqual(code, 0, record)
        self.assertEqual(record["session_id"], SESSION)

    def test_wrong_session_is_refused(self):
        _, _, previous, _ = self.invoke()
        code, record, _, _ = self.invoke(case="wrong_session", extra=("--resume", str(previous)))
        self.assertEqual(code, 1)
        self.assertIn("different session", record["error"])

    def test_resume_wrong_provider_or_model_rejected_before_launch(self):
        _, _, previous, _ = self.invoke()
        code, record, _, error = self.invoke("codex", extra=("--resume", str(previous)))
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        self.assertIn("provider", error)
        code, record, _, error = self.invoke(extra=("--resume", str(previous), "--model", "new-model"))
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        self.assertIn("requested_model", error)

    def test_timeout_records_failure(self):
        code, record, _, _ = self.invoke(case="timeout", extra=("--timeout", "1"))
        self.assertEqual(code, 1)
        self.assertIn("timed out", record["error"])

    def test_unique_artifacts_and_failed_round_does_not_reuse_reply(self):
        _, _, first, _ = self.invoke()
        code, record, second, _ = self.invoke(case="empty")
        self.assertNotEqual(first, second)
        self.assertEqual(code, 1)
        self.assertNotIn("response", record)

    def test_snapshot_covers_staged_unstaged_deleted_and_new_files(self):
        (self.repo / "existing.py").write_text("staged version\n")
        self.git("add", "existing.py")
        (self.repo / "existing.py").write_text("unstaged final version\n")
        (self.repo / "delete.py").unlink()
        (self.repo / "new.py").write_text("brand new\n")
        snap = runner.snapshot(self.repo, self.base)
        self.assertEqual({f["path"] for f in snap["files"]}, {"existing.py", "delete.py", "new.py"})
        self.assertEqual(next(f for f in snap["files"] if f["path"] == "delete.py")["kind"], "deleted")
        self.assertEqual(next(f for f in snap["files"] if f["path"] == "existing.py")["sha256"],
                         runner.digest((self.repo / "existing.py").read_bytes()))

    def test_inspection_requires_other_provider_and_fresh_session(self):
        code, _, _, error = self.invoke(mode="inspect", extra=("--base", self.base, "--provider", "claude"))
        self.assertEqual(code, 1)
        self.assertIn("opposite the builder", error)
        _, _, previous, _ = self.invoke()
        code, _, _, error = self.invoke(mode="inspect", extra=("--base", self.base, "--resume", str(previous)))
        self.assertEqual(code, 1)
        self.assertIn("fresh session", error)

    def test_changed_code_during_inspection_fails(self):
        (self.repo / "new.py").write_text("original new file")
        code, record, _, _ = self.invoke(mode="inspect", case="mutate_code", extra=("--base", self.base))
        self.assertEqual(code, 1)
        self.assertIn("Code changed", record["error"])

    def test_build_requires_explicit_review_override_and_clean_tree(self):
        code, _, _, error = self.invoke(mode="build", extra=("--proof", "python -m unittest"))
        self.assertEqual(code, 1)
        self.assertIn("--approval", error)
        (self.repo / "user_work.py").write_text("preserve me")
        code, _, _, error = self.invoke(mode="build", extra=("--unreviewed-spec", "--proof", "test"))
        self.assertEqual(code, 1)
        self.assertIn("clean checkout", error)
        self.assertEqual((self.repo / "user_work.py").read_text(), "preserve me")

    def test_build_resume_keeps_initial_baseline_and_existing_build_changes(self):
        extra = ("--builder", "codex", "--unreviewed-spec", "--proof", "python -m unittest")
        code, record, path, _ = self.invoke(mode="build", case="build", extra=extra)
        self.assertEqual(code, 0, record)
        self.assertEqual(record["base"], self.base)
        code, record, _, _ = self.invoke(mode="build", case="build", extra=extra+("--resume", str(path)))
        self.assertEqual(code, 0, record)
        self.assertEqual(record["base"], self.base)
        (self.repo / "user_work.py").write_text("intervening edit")
        code, _, _, error = self.invoke(mode="build", case="build", extra=extra+("--resume", str(path)))
        self.assertEqual(code, 1)
        self.assertIn("Checkout changed", error)

    def test_artifacts_cannot_contaminate_target_checkout(self):
        code, _, _, error = self.invoke(extra=("--artifacts", str(self.repo / "runs")))
        self.assertEqual(code, 1)
        self.assertIn("outside", error)
        code, _, _, error = self.invoke(mode="research", extra=(
            "--brief", str(self.brief), "--model", "gemini-test",
            "--artifacts", str(self.repo / "runs")))
        self.assertEqual(code, 1)
        self.assertIn("outside", error)

    # Team build: Gemini frontend builder, staged handoffs, authorship routing and budgets.

    def test_frontend_build_from_both_hosts_uses_bounded_agy_flags(self):
        for host in runner.PROVIDERS:
            with self.subTest(host=host):
                code, record, path, _ = self.frontend(host)
                self.assertEqual(code, 0, record)
                self.assertEqual((record["provider"], record["roles"]["host"], record["roles"]["inspector"]),
                                 ("agy", host, host))
                self.assertEqual((record["changed_files"], record["authorship"]), (["ui.js"], {"ui.js": ["agy"]}))
                self.assertEqual(record["observed_permission_mode"], "accept-edits")
                argv = json.loads((path.parent / "command.json").read_text())
                self.assertEqual(argv[argv.index("--mode") + 1], "accept-edits")
                self.assertIn("--sandbox", argv)
                for flag in ("--dangerously-skip-permissions", "--continue", "-c", "--conversation"):
                    self.assertNotIn(flag, argv)
                prompt = (path.parent / "prompt.txt").read_text()
                for text in (str(self.plan), "npm test", "BACKEND_DEPENDENCY", f"JOB BASELINE COMMIT: {self.base}",
                             f"Your checkout and working directory is {self.repo}", "search outside it",
                             "do not open it", "Run it only if the plan states"):
                    self.assertIn(text, prompt)
                self.reset()

    def test_frontend_requires_listed_gemini_model_before_launch(self):
        for extra in ((), ("--model", "claude-test"), ("--model", "gemini-test", "--effort", "max")):
            code, record, _, _ = self.invoke(mode="build", extra=(
                "--builder", "agy", "--unreviewed-spec", "--proof", "t", *extra))
            self.assertEqual(code, 1)
            self.assertIsNone(record)
        code, record, _, _ = self.frontend(extra=("--model", "gemini-absent"))
        self.assertEqual((code, record["status"]), (1, "failed"))
        self.assertIn("models.txt", record["error"])
        self.assertFalse(any("accept-edits" in call for call in self.calls()))

    def test_gemini_builder_rejects_conflicting_provider_before_launch(self):
        code, record, _, error = self.invoke(mode="build", extra=(
            "--builder", "agy", "--provider", "codex", "--unreviewed-spec", "--proof", "t"))
        self.assertEqual((code, record), (1, None))
        self.assertIn("omit --provider", error)
        self.assertEqual(self.calls(), [])

    def test_frontend_non_completion_never_completes_or_falls_back(self):
        expected = {"fe_dependency": "blocked", "fe_incomplete": "incomplete", "fe_mock": "failed",
                    "fe_noproof": "failed", "fe_noevidence": "failed", "malformed": "failed",
                    "turn_failed": "failed", "incomplete": "failed", "exit": "failed", "empty": "failed",
                    "wrong_session": "completed", "fe_timeout": "failed", "fe_denied": "failed"}
        for case, status in expected.items():
            with self.subTest(case=case):
                extra = ("--timeout", "2") if case == "fe_timeout" else ()
                code, record, _, _ = self.frontend(case=case, extra=extra)
                self.assertEqual(record["status"], status, record.get("error"))
                self.assertEqual(code, 0 if status == "completed" else 1)
                self.reset()
        for call in self.calls():  # only agy probes and agy builds; never Claude/Codex
            self.assertTrue(call in (["--version"], ["models"]) or "accept-edits" in call, call)
        _, blocked, _, _ = self.frontend(case="fe_dependency")
        self.assertEqual(blocked["response"]["dependencies"][0]["needed"], "A total field in the response")
        self.reset()
        _, denied, _, _ = self.frontend(case="fe_denied")
        self.assertIn("ListDir", denied["error"])
        self.reset()
        _, timed_out, _, _ = self.frontend(case="fe_timeout", extra=("--timeout", "2"))
        self.assertIn("timed out", timed_out["error"])
        self.assertIn("partial.js", timed_out["changed_files"])

    def test_non_frontend_job_never_launches_gemini(self):
        code, record, path, _ = self.build("codex")
        self.assertEqual(code, 0, record)
        code, inspection, _, _ = self.invoke(mode="inspect", extra=("--after", str(path)))
        self.assertEqual((code, inspection["provider"], inspection["route"]), (0, "claude", ["claude"]))
        self.assertFalse(any("accept-edits" in call or call == ["models"] for call in self.calls()))

    def test_mixed_work_routes_inspector_opposite_primary_for_either_host(self):
        for host, primary in (("claude", "codex"), ("codex", "claude"), ("claude", "claude"), ("codex", "codex")):
            with self.subTest(host=host, primary=primary):
                if primary == host:  # host-direct backend recorded by stage
                    _, _, start, _ = self.invoke(host, "stage", extra=("--unreviewed-spec",))
                    (self.repo / "api.py").write_text("total = 3\n")
                    code, first, first_path, _ = self.invoke(host, "stage", extra=(
                        "--unreviewed-spec", "--after", str(start)))
                    self.assertEqual((first["author"], first["changed_files"]), (host, ["api.py"]))
                else:
                    code, first, first_path, _ = self.build(primary, host)
                self.assertEqual(code, 0, first)
                code, ui, ui_path, _ = self.frontend(host, extra=("--after", str(first_path)))
                self.assertEqual(code, 0, ui)
                self.assertEqual(ui["authorship"]["ui.js"], ["agy"])
                self.assertIn(next(iter(first["authorship"])), (ui_path.parent / "prompt.txt").read_text())
                code, _, _, error = self.invoke(host, "inspect", extra=(
                    "--after", str(ui_path), "--provider", primary))
                self.assertIn("cannot inspect it independently", error)
                code, inspection, _, _ = self.invoke(host, "inspect", extra=("--after", str(ui_path)))
                self.assertEqual((code, inspection["provider"]), (0, runner.other(primary)))
                self.reset()

    def test_gemini_only_uses_fresh_host_provider_inspector(self):
        for host in runner.PROVIDERS:
            with self.subTest(host=host):
                self.reset()
                _, record, path, _ = self.frontend(host)
                # No fictitious Claude/Codex implementation role: Gemini alone authored the code.
                self.assertEqual((record["roles"]["builder"], record["roles"]["inspector"]), ("agy", host))
                self.assertEqual(set().union(*record["authorship"].values()), {"agy"})
                code, inspection, _, _ = self.invoke(host, "inspect", extra=("--after", str(path)))
                self.assertEqual((code, inspection["provider"], inspection["self_authored"]), (0, host, []))
                code, extra_review, _, _ = self.invoke(host, "inspect", extra=(
                    "--after", str(path), "--provider", runner.other(host)))
                self.assertEqual((code, extra_review["inspection_round"]), (0, 2))

    def test_backend_dependency_activates_primary_and_reroutes_inspection(self):
        feedback = self.root / "contract.md"
        feedback.write_text("Confirmed: GET /items now returns {items, total}.\n")
        for host in runner.PROVIDERS:
            with self.subTest(host=host):
                code, blocked, blocked_path, _ = self.frontend(host, case="fe_dependency")
                self.assertEqual((code, blocked["status"]), (1, "blocked"))
                self.assertEqual(runner.inspection_route(host, blocked["authorship"]), [host])
                code, wrong, wrong_path, _ = self.frontend(host, case="wrong_session", extra=(
                    "--resume", str(blocked_path)))
                self.assertIn("different conversation", wrong["error"])
                self.assertEqual(wrong["changed_files"], [])
                # The failed attempt is now the job's latest step; the blocked result still supplies the session.
                (self.repo / "api.py").write_text("def items(): return {'items': [], 'total': 0}\n")
                code, backend, backend_path, _ = self.invoke(host, "stage", extra=(
                    "--unreviewed-spec", "--after", str(wrong_path)))
                self.assertEqual((backend["author"], backend["changed_files"]), (host, ["api.py"]))
                code, done, done_path, _ = self.frontend(host, extra=(
                    "--after", str(backend_path), "--resume", str(blocked_path), "--feedback", str(feedback)))
                self.assertEqual((code, done["status"], done["session_id"]), (0, "completed", SESSION))
                argv = json.loads((done_path.parent / "command.json").read_text())
                self.assertEqual(argv[argv.index("--conversation") + 1], SESSION)
                self.assertIn("total", (done_path.parent / "prompt.txt").read_text())
                code, inspection, _, _ = self.invoke(host, "inspect", extra=("--after", str(done_path)))
                self.assertEqual((code, inspection["provider"]), (0, runner.other(host)))
                self.reset()

    def test_one_writer_and_only_recorded_changes_continue(self):
        lock = Path(self.git("rev-parse", "--absolute-git-dir").strip()) / "claudex-build.lock"
        lock.write_text("held")
        for mode_call in (lambda: self.frontend(), lambda: self.invoke(mode="stage", extra=("--unreviewed-spec",))):
            code, _, _, error = mode_call()
            self.assertEqual(code, 1)
            self.assertIn("one writer", error)
        lock.unlink()
        code, ui, ui_path, _ = self.frontend()
        self.assertEqual(code, 0, ui)
        self.assertFalse(lock.exists())
        (self.repo / "user_work.py").write_text("unrelated")
        code, _, _, error = self.build("codex", extra=("--after", str(ui_path)))
        self.assertEqual(code, 1)
        self.assertIn("Checkout changed", error)
        self.assertEqual((self.repo / "user_work.py").read_text(), "unrelated")
        (self.repo / "user_work.py").unlink()
        _, _, approval, _ = self.invoke()
        self.plan.write_text("# Work order\nContract v2: GET /items returns a total.\n")
        code, _, _, error = self.frontend(extra=("--after", str(ui_path), "--approval", str(approval)))
        self.assertEqual(code, 1)
        self.assertIn("Plan changed after approval", error)

    def test_index_only_mode_change_is_attributed_and_reroutes(self):
        (self.repo / "tool.sh").write_text("echo 1\n")
        self.git("add", "tool.sh")
        self.git("commit", "-qm", "tool")
        self.git("config", "core.fileMode", "false")
        _, ui, ui_path, _ = self.frontend(env={"FAKE_UI_FILE": "tool.sh", "FAKE_UI": "echo 2\n"})
        self.git("update-index", "--chmod=+x", "tool.sh")
        code, staged, staged_path, _ = self.invoke("claude", "stage", extra=(
            "--unreviewed-spec", "--after", str(ui_path)))
        self.assertEqual((code, staged["changed_files"]), (0, ["tool.sh"]))
        self.assertEqual(staged["authorship"]["tool.sh"], ["agy", "claude"])
        code, inspection, _, _ = self.invoke("claude", "inspect", extra=("--after", str(staged_path)))
        self.assertEqual((code, inspection["provider"]), (0, "codex"))

    @unittest.skipIf(os.name == "nt", "Windows has no worktree executable bits")
    def test_posix_worktree_chmod_is_attributed(self):
        _, _, ui_path, _ = self.frontend()
        os.chmod(self.repo / "ui.js", 0o755)
        code, staged, _, _ = self.invoke("codex", "stage", extra=("--unreviewed-spec", "--after", str(ui_path)))
        self.assertEqual((code, staged["authorship"]["ui.js"]), (0, ["agy", "codex"]))

    @unittest.skipIf(os.name == "nt", "Windows has no worktree executable bits")
    def test_posix_change_between_nonzero_masks_is_attributed(self):
        _, ui, ui_path, _ = self.frontend(env={"FAKE_UI_MODE": "700"})
        self.assertEqual(runner.inspection_route("claude", ui["authorship"]), ["claude"])
        os.chmod(self.repo / "ui.js", 0o710)
        code, staged, staged_path, _ = self.invoke("claude", "stage", extra=(
            "--unreviewed-spec", "--after", str(ui_path)))
        self.assertEqual((code, staged["changed_files"]), (0, ["ui.js"]))
        self.assertNotEqual(staged["snapshot"]["sha256"], ui["snapshot"]["sha256"])
        code, inspection, _, _ = self.invoke("claude", "inspect", extra=("--after", str(staged_path)))
        self.assertEqual((code, inspection["provider"]), (0, "codex"))

    def test_superseded_steps_cannot_reset_job_budgets(self):
        _, _, first, _ = self.frontend()
        code, later, later_path, _ = self.invoke(mode="stage", extra=(
            "--unreviewed-spec", "--after", str(first), "--fix-round", "1"))
        self.assertEqual((code, later["changed_files"], later["fix_round"]), (0, [], 1))
        (self.repo / "unrecorded.txt").write_text("edit outside any step")
        code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(later_path)))
        self.assertIn("Checkout changed since the recorded step", error)
        (self.repo / "unrecorded.txt").unlink()
        for _ in range(2):
            self.assertEqual(self.invoke(mode="inspect", extra=("--after", str(later_path)))[0], 0)
        # The checkout still matches the ancestor, but only the latest step may continue or be inspected.
        code, _, _, error = self.build("codex", extra=("--after", str(first), "--fix-round", "0"))
        self.assertIn("latest step", error)
        code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(first)))
        self.assertIn("latest step", error)
        # A resumed build's position must be the latest step too.
        self.reset()
        _, _, build1, _ = self.build("codex")
        self.assertEqual(self.build("codex", extra=("--resume", str(build1)))[0], 0)
        code, _, _, error = self.build("codex", extra=("--resume", str(build1)))
        self.assertIn("latest step", error)

    def test_staged_content_differing_from_worktree_is_fingerprinted_and_not_inspected(self):
        (self.repo / "page.js").write_text("A\n")
        self.git("add", "page.js")
        self.git("commit", "-qm", "page")
        _, ui, ui_path, _ = self.frontend(env={"FAKE_UI_FILE": "page.js", "FAKE_UI": "B\n"})
        # Stage different versions of a text file and a binary asset, then restore other working-tree bytes.
        (self.repo / "page.js").write_text("C\n")
        (self.repo / "logo.png").write_bytes(b"\x89PNG\x00staged")
        self.git("add", "page.js", "logo.png")
        (self.repo / "page.js").write_text("B\n")
        (self.repo / "logo.png").write_bytes(b"\x89PNG\x00worktree")
        code, _, _, error = self.build("codex", extra=("--after", str(ui_path)))
        self.assertIn("Checkout changed", error)
        code, staged, staged_path, _ = self.invoke("claude", "stage", extra=(
            "--unreviewed-spec", "--after", str(ui_path)))
        self.assertEqual((code, staged["changed_files"]), (0, ["logo.png", "page.js"]))
        self.assertEqual(staged["authorship"]["page.js"], ["agy", "claude"])
        # The inspector reads the working tree, so a divergent index is refused rather than half-inspected.
        code, record, _, error = self.invoke("claude", "inspect", extra=("--after", str(staged_path)))
        self.assertEqual((code, record), (1, None))
        self.assertIn("Staged content differs from the working tree for ['logo.png', 'page.js']", error)
        self.git("add", "page.js", "logo.png")
        code, agreed, agreed_path, _ = self.invoke("claude", "stage", extra=(
            "--unreviewed-spec", "--after", str(staged_path)))
        self.assertEqual(code, 0, agreed)
        code, inspection, inspection_path, _ = self.invoke("claude", "inspect", extra=("--after", str(agreed_path)))
        self.assertEqual((code, inspection["provider"]), (0, "codex"))
        self.assertIn("STAGED DIFF", (inspection_path.parent / "prompt.txt").read_text())

    def test_snapshot_lists_both_paths_of_staged_rename(self):
        self.git("config", "diff.renames", "true")
        self.git("mv", "existing.py", "moved.py")
        files = {f["path"]: f for f in runner.snapshot(self.repo, self.base)["files"]}
        self.assertEqual(files["existing.py"]["kind"], "deleted")
        self.assertIn("moved.py", files)

    def test_fix_and_inspection_budgets_are_job_wide(self):
        _, _, first, _ = self.frontend()
        code, fix1, fix1_path, _ = self.build("codex", extra=("--after", str(first), "--fix-round", "1"))
        self.assertEqual((code, fix1["fix_round"]), (0, 1))
        code, _, _, error = self.frontend(extra=("--after", str(fix1_path), "--fix-round", "0"))
        self.assertIn("cannot be reset", error)
        code, fix2, fix2_path, _ = self.frontend(extra=("--after", str(fix1_path), "--fix-round", "2"),
                                                 env={"FAKE_UI": "render(2);\n"})
        self.assertEqual((code, fix2["changed_files"]), (0, ["ui.js"]))
        code, _, _, error = self.frontend(extra=("--after", str(fix2_path), "--fix-round", "3"))
        self.assertIn("Fix budget exhausted", error)
        # Two proof-driven fix rounds leave both inspection rounds available.
        for number in (1, 2):
            code, inspection, _, _ = self.invoke(mode="inspect", extra=("--after", str(fix2_path)))
            self.assertEqual((code, inspection["provider"], inspection["inspection_round"]), (0, "claude", number))
        code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(fix2_path)))
        self.assertIn("Inspection budget exhausted", error)
        # A provider switch inherits both counters instead of resetting them.
        code, later, later_path, _ = self.frontend(extra=("--after", str(fix2_path)))
        self.assertEqual((code, later["fix_round"], later["inspection_rounds"]), (0, 2, 2))
        code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(later_path)))
        self.assertIn("Inspection budget exhausted", error)
        # Later steps supersede older ones, so their inspection budget cannot be reused.
        code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(first)))
        self.assertIn("latest step", error)

    def test_claude_and_codex_authorship_requires_counted_cross_inspection(self):
        _, _, claude_path, _ = self.build("claude")
        code, codex, codex_path, _ = self.build("codex", extra=("--after", str(claude_path)))
        self.assertEqual(codex["authorship"], {"built_claude.py": ["claude"], "built_codex.py": ["codex"]})
        code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(codex_path)))
        self.assertIn("both authored", error)
        for number in (1, 2):
            for provider in ("codex", "claude"):
                code, inspection, _, _ = self.invoke(mode="inspect", extra=(
                    "--after", str(codex_path), "--provider", provider))
                self.assertEqual((code, inspection["inspection_round"]), (0, number))
                self.assertEqual(inspection["self_authored"], [f"built_{provider}.py"])
        for provider in ("codex", "claude"):  # alternating cannot reuse a completed pair
            code, _, _, error = self.invoke(mode="inspect", extra=("--after", str(codex_path), "--provider", provider))
            self.assertIn("Inspection budget exhausted", error)

    def test_missing_browser_access_is_a_verification_gap(self):
        code, record, _, _ = self.frontend(case="fe_gap")
        self.assertEqual((code, record["status"]), (0, "completed"))
        self.assertEqual([(g["kind"], g["status"]) for g in record["verification_gaps"]], [("browser", "NOT_RUN")])

    def test_non_ascii_result_prints_on_legacy_console(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with patch.object(runner, "cli_prefix", return_value=[sys.executable, str(self.cli)]), \
             patch.dict(os.environ, {"FAKE_CASE": "unicode"}), patch.object(sys, "stdout", stream):
            code = runner.main(["review", "--host", "claude", "--repo", str(self.repo), "--plan",
                                str(self.plan), "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
