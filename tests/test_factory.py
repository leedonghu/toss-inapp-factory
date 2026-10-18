import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.toss_harness import TossHarnessIntegration
from orchestrator.orchestrator import TossAIFactoryOrchestrator, ROOT, load_config, DEFAULT_CONFIG, main
from orchestrator.process import CommandError, resolve_command, run_command
from orchestrator.task_schema import TaskMessage, TaskStatus


class FactoryTests(unittest.TestCase):
    """실제 AI CLI 없이 에이전트·npm 호출을 가짜로 바꿔 파이프라인의 fail-closed 동작을 검증한다."""

    def setUp(self):
        # 테스트마다 저장소 루트 아래에 임시 프로젝트 디렉터리를 만든다 (종료 시 자동 삭제).
        self.temp = tempfile.TemporaryDirectory(prefix="factory-test-", dir=ROOT)
        assert Path(self.temp.name).resolve().is_relative_to(ROOT.resolve())
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.factory = TossAIFactoryOrchestrator(self.project)
        self.harness = TossHarnessIntegration(self.project)

    def write(self, name, value):
        """프로젝트 안에 파일을 쓴다. 문자열이 아니면 JSON으로 직렬화한다."""
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")

    def fake_agent(self, agent, prompt, index):
        """run_agent 대역. 단계 번호(1=PLAN, 2=IMPLEMENT, 3/4=리뷰)에 맞는 정상 산출물을 만든다."""
        if index == 1:
            self.write("PRD.md", "Test app")
            (self.factory.run_dir / "tasks.json").write_text(json.dumps({"tasks": [
                {"title": "Implement", "acceptance_criteria": ["Tests pass"]}]}), encoding="utf-8")
        elif index == 2:
            self.write("package.json", {"scripts": {key: "test" for key in
                       ("build", "bundle", "test", "lint", "typecheck")}})
        else:
            action = "UI_REVIEW" if index == 3 else "CROSS_REVIEW"
            (self.factory.run_dir / f"{action}.json").write_text(json.dumps(
                {"passed": True, "findings": [], "checks": ["Inspected code"]}), encoding="utf-8")

    def run_pipeline(self, agent=None, scripts=None, resume=None):
        """preflight·에이전트·npm 스크립트를 패치한 채 파이프라인을 실행한다.

        agent / scripts로 각 대역을 바꿔 실패 시나리오를 만들 수 있다.
        기본 npm 대역은 bundle 스크립트에서 app.ait를 생성한다.
        """
        def default_script(name):
            if name == "bundle":
                self.write("app.ait", "test bundle")
        with patch.object(self.factory, "preflight"), patch.object(self.factory, "run_agent", side_effect=agent or self.fake_agent), patch.object(TossHarnessIntegration, "run_script", side_effect=scripts or default_script), contextlib.redirect_stdout(io.StringIO()):
            return self.factory.run_full_pipeline("test", resume=resume)

    def test_resume_each_failed_stage(self):
        for failed_index in range(1, 6):
            with self.subTest(stage=failed_index):
                def agent(*args):
                    if args[-1] == failed_index:
                        raise CommandError("interrupted")
                    self.fake_agent(*args)
                def script(name):
                    if name == "bundle":
                        raise CommandError("bundle failed")
                with self.assertRaises(CommandError):
                    self.run_pipeline(agent=agent, scripts=script)
                old_run = self.factory.run_dir
                old_records = {p.name: p.read_bytes() for p in old_run.iterdir()}
                calls = []
                def retry(*args):
                    calls.append(args[-1])
                    self.fake_agent(*args)
                result = self.run_pipeline(agent=retry, resume=old_run.name)
                self.assertEqual(result.status, TaskStatus.SUCCESS)
                self.assertEqual(calls, list(range(failed_index, 5)))
                self.assertNotEqual(old_run, self.factory.run_dir)
                self.assertEqual(old_records, {p.name: p.read_bytes() for p in old_run.iterdir()})

    def test_resume_does_not_reuse_failed_review(self):
        def fail(*args):
            self.fake_agent(*args)
            if args[-1] == 3:
                raise CommandError("failed after writing report")
        with self.assertRaises(CommandError):
            self.run_pipeline(agent=fail)
        with self.assertRaisesRegex(ValueError, "Missing"):
            self.run_pipeline(agent=lambda *args: None, resume=self.factory.run_dir.name)

    def test_resume_rejects_missing_plan_artifact(self):
        def fail(*args):
            if args[-1] == 2:
                raise CommandError("failed")
            self.fake_agent(*args)
        with self.assertRaises(CommandError):
            self.run_pipeline(agent=fail)
        (self.factory.run_dir / "tasks.json").write_text('{}')
        with self.assertRaisesRegex(ValueError, "tasks"):
            self.run_pipeline(resume=self.factory.run_dir.name)

    def test_resume_rejects_complete_run_and_outside_path(self):
        self.run_pipeline()
        with self.assertRaisesRegex(ValueError, "already complete"):
            self.run_pipeline(resume=self.factory.run_dir.name)
        with self.assertRaises(ValueError):
            self.run_pipeline(resume="../outside")

    def test_success_checks_and_bundle(self):
        calls = []
        def script(name):
            calls.append(name)
            if name == "bundle":
                self.write("app.ait", "bundle")
        result = self.run_pipeline(scripts=script)
        self.assertEqual(result.status, TaskStatus.SUCCESS)
        self.assertEqual(calls, ["typecheck", "lint", "test", "build"] * 2 + ["bundle"])
        self.assertTrue(Path(result.output_artifacts[0]).is_file())
        self.assertEqual(len(list(self.factory.run_dir.glob("[0-9][0-9]-*.json"))), 5)

    def test_manual_checks_do_not_block_and_are_collected(self):
        def agent(*args):
            self.fake_agent(*args)
            if args[-1] == 4:
                (self.factory.run_dir / "CROSS_REVIEW.json").write_text(json.dumps(
                    {"passed": True, "findings": [], "checks": ["Read config"],
                     "manual_checks": ["Test copy on a Toss test build"]}), encoding="utf-8")
        result = self.run_pipeline(agent=agent)
        self.assertEqual(result.status, TaskStatus.SUCCESS)
        manual = json.loads((self.factory.run_dir / "manual_checks.json").read_text(encoding="utf-8"))
        self.assertEqual(manual, {"UI_REVIEW": [], "CROSS_REVIEW": ["Test copy on a Toss test build"]})

    def test_invalid_manual_checks_rejected(self):
        def agent(*args):
            self.fake_agent(*args)
            if args[-1] == 3:
                (self.factory.run_dir / "UI_REVIEW.json").write_text(
                    '{"passed":true,"findings":[],"checks":["x"],"manual_checks":"device"}')
        with self.assertRaisesRegex(ValueError, "manual_checks"):
            self.run_pipeline(agent=agent)

    def test_review_prompt_points_to_npm_logs(self):
        prompts = {}
        def agent(name, prompt, index):
            prompts[index] = prompt
            self.fake_agent(name, prompt, index)
        def script(name):
            # 실제 run_command 대신, 하네스가 지정한 접두사로 로그 파일만 만든다.
            Path(f"{self.factory.run_dir / f'02-npm'}-{name}.stdout.log").write_text("ok", encoding="utf-8")
            if name == "bundle":
                self.write("app.ait", "bundle")
        self.run_pipeline(agent=agent, scripts=script)
        self.assertIn("02-npm-test.stdout.log", prompts[3])
        self.assertIn("manual_checks", prompts[4])

    def test_resume_after_implement_reruns_checks(self):
        def fail(*args):
            if args[-1] == 4:
                raise CommandError("rejected")
            self.fake_agent(*args)
        with self.assertRaises(CommandError):
            self.run_pipeline(agent=fail)
        calls = []
        def script(name):
            calls.append(name)
            if name == "bundle":
                self.write("app.ait", "bundle")
        self.run_pipeline(scripts=script, resume=self.factory.run_dir.name)
        self.assertEqual(calls, ["typecheck", "lint", "test", "build"] * 2 + ["bundle"])

    def test_harness_logs_npm_output(self):
        self.write("package.json", {"scripts": {"test": "vitest run"}})
        self.harness.log_prefix = self.project / "02-npm"
        with patch("integrations.toss_harness.run_command") as run:
            self.harness.run_script("test")
        self.assertEqual(run.call_args.kwargs["log_prefix"], f"{self.project / '02-npm'}-test")

    def test_cli_failure_stops_pipeline(self):
        calls = []
        def fail(agent, prompt, index):
            calls.append(index)
            raise CommandError("CLI failed")
        with self.assertRaises(CommandError):
            self.run_pipeline(agent=fail)
        self.assertEqual(calls, [1])
        record = json.loads((self.factory.run_dir / "01-PLAN.json").read_text())
        self.assertEqual(record["status"], "FAILED")

    def test_build_failure_stops_before_review(self):
        calls = []
        def agent(*args):
            calls.append(args[-1])
            self.fake_agent(*args)
        with self.assertRaises(CommandError):
            self.run_pipeline(agent=agent, scripts=lambda _: (_ for _ in ()).throw(CommandError("bad build")))
        self.assertEqual(calls, [1, 2])

    def test_rejected_review_blocks_bundle(self):
        calls = []
        def reject(*args):
            calls.append(args[-1])
            self.fake_agent(*args)
            if args[-1] == 3:
                (self.factory.run_dir / "UI_REVIEW.json").write_text(json.dumps(
                    {"passed": False, "findings": ["broken UI"], "checks": ["layout"]}))
        with self.assertRaises(ValueError):
            self.run_pipeline(agent=reject)
        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(json.loads((self.factory.run_dir / "03-UI_REVIEW.json").read_text())["status"], "NEEDS_FIX")

    def test_string_passed_is_rejected(self):
        def invalid(*args):
            self.fake_agent(*args)
            if args[-1] == 3:
                (self.factory.run_dir / "UI_REVIEW.json").write_text('{"passed":"false","checks":["x"],"findings":[]}')
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.run_pipeline(agent=invalid)

    def test_old_reports_are_not_reused(self):
        self.write("PRD.md", "old")
        self.write("tasks.json", {"tasks": [{"title": "old"}]})
        with self.assertRaisesRegex(ValueError, "Missing"):
            self.run_pipeline(agent=lambda *args: None)

    def test_invalid_task_schema_stops(self):
        def invalid(*args):
            self.fake_agent(*args)
            (self.factory.run_dir / "tasks.json").write_text('{"tasks":[{"title":"x"}]}')
        with self.assertRaisesRegex(ValueError, "acceptance_criteria"):
            self.run_pipeline(agent=invalid)

    def test_stale_bundle_rejected(self):
        self.write("old.ait", "old")
        with patch.object(self.harness, "run_script"), self.assertRaises(CommandError):
            self.harness.build_ait_bundle()

    def test_empty_bundle_rejected(self):
        with patch.object(self.harness, "run_script", side_effect=lambda _: self.write("empty.ait", "")), self.assertRaises(CommandError):
            self.harness.build_ait_bundle()

    def test_missing_script_is_error(self):
        self.write("package.json", {"scripts": {"lint": "echo lint"}})
        with self.assertRaisesRegex(ValueError, "typecheck"):
            self.harness.run_typecheck_and_lint()

    def test_malformed_package_is_error(self):
        self.write("package.json", [])
        with self.assertRaisesRegex(ValueError, "scripts object"):
            self.harness.run_script("build")

    def test_scaffold_rejects_shell_input(self):
        with self.assertRaises(ValueError):
            self.harness.init_miniapp_template("app & echo injected")

    def test_default_path_is_current_repository(self):
        self.assertEqual(TossAIFactoryOrchestrator().project_dir, ROOT / "projects" / "roulette")

    def test_check_does_not_create_project(self):
        nonexistent = self.project / "new"
        with patch("orchestrator.orchestrator.resolve_command", return_value=["fake"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(nonexistent), "--check"]), 0)
        self.assertFalse(nonexistent.exists())

    def test_missing_cli_fails_preflight(self):
        with patch("orchestrator.orchestrator.resolve_command", side_effect=CommandError("missing")):
            with self.assertRaisesRegex(CommandError, "Preflight"):
                self.factory.preflight()

    def test_npm_shim_runs_through_node(self):
        script = self.project / "node_modules" / "@scope" / "tool" / "bin" / "tool.js"
        script.parent.mkdir(parents=True)
        script.write_text("", encoding="utf-8")
        self.write("tool.cmd", '@ECHO off\r\n"%_prog%"  "%dp0%\\node_modules\\@scope\\tool\\bin\\tool.js" %*\r\n')
        found = {"tool": str(self.project / "tool.cmd"), "node": "node.exe"}
        with patch("orchestrator.process.shutil.which", side_effect=found.get):
            self.assertEqual(resolve_command(["tool", "exec", "-"]), ["node.exe", str(script), "exec", "-"])

    def test_unknown_batch_wrapper_is_rejected(self):
        self.write("tool.bat", "@echo off\r\nsomething.exe %*\r\n")
        found = {"tool": str(self.project / "tool.bat"), "node": "node.exe"}
        with patch("orchestrator.process.shutil.which", side_effect=found.get):
            with self.assertRaisesRegex(CommandError, "batch wrapper"):
                resolve_command(["tool"])

    def test_invalid_workflow(self):
        config = load_config(DEFAULT_CONFIG)
        config["workflows"]["default_pipeline"].pop()
        self.write("bad.json", config)
        with self.assertRaises(ValueError):
            load_config(self.project / "bad.json")

    def test_message_round_trip(self):
        original = TaskMessage(status=TaskStatus.NEEDS_FIX)
        self.assertEqual(TaskMessage.from_json(original.to_json()), original)

    # 아래 테스트들은 실제 파이썬 하위 프로세스를 띄워 run_command를 검증한다.
    def test_agent_prompt_argument_survives_real_process(self):
        prompt = '--mode 한글 "quotes" & | %PATH%\n{prompt}'
        self.factory.run_dir = self.project
        agent = self.factory.config["agents"]["antigravity"]
        self.assertEqual(agent["exec_args"][-1], "-p={prompt}")
        agent["cli_command"] = sys.executable
        agent["exec_args"] = ["-c", "import json,sys; print(json.dumps([sys.argv[1:], sys.stdin.read()]))", *agent["exec_args"]]
        output = self.factory.run_agent("antigravity", prompt, 3)
        args, stdin = json.loads(output)
        self.assertEqual(args, ["--mode", "accept-edits", "--output-format", "json", "-p=" + prompt])
        self.assertEqual(stdin, "")

    def test_agent_stdin_prompt_survives_real_process(self):
        prompt = '한글 "quotes"\nsecond line'
        self.factory.run_dir = self.project
        self.factory.config["agents"]["claude"] = {
            "cli_command": sys.executable,
            "exec_args": ["-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        }
        self.assertEqual(self.factory.run_agent("claude", prompt, 1), prompt)

    def test_zero_exit_permission_denial_is_failure(self):
        self.factory.run_dir = self.project
        response = json.dumps({"status": "SUCCESS", "response": "", "denied_actions": [
            {"action": "command", "display_name": "RunCommand"}]})
        with patch("orchestrator.orchestrator.run_command", return_value=response):
            with self.assertRaisesRegex(CommandError, "tool permissions denied"):
                self.factory.run_agent("antigravity", "Review app", 3)

    def test_json_response_without_denials_is_returned(self):
        self.factory.run_dir = self.project
        response = '{"status":"SUCCESS","denied_actions":[]}'
        with patch("orchestrator.orchestrator.run_command", return_value=response):
            self.assertEqual(self.factory.run_agent("antigravity", "Review app", 3), response)

    def test_real_process_unicode_stdin(self):
        prompt = '한글 "quotes" & | %PATH%\nsecond line'
        output = run_command([sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"], self.project, input_text=prompt)
        self.assertEqual(output, prompt)

    def test_real_process_nonzero(self):
        with self.assertRaisesRegex(CommandError, "exited 7"):
            run_command([sys.executable, "-c", "raise SystemExit(7)"], self.project)

    def test_real_process_timeout(self):
        with self.assertRaisesRegex(CommandError, "timed out"):
            run_command([sys.executable, "-c", "import time; time.sleep(10)"], self.project, timeout=0.05)


if __name__ == "__main__":
    unittest.main()
