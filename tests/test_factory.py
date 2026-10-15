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
from orchestrator.process import CommandError, run_command
from orchestrator.task_schema import TaskMessage, TaskStatus


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory-test-", dir=ROOT)
        assert Path(self.temp.name).resolve().is_relative_to(ROOT.resolve())
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.factory = TossAIFactoryOrchestrator(self.project)
        self.harness = TossHarnessIntegration(self.project)

    def write(self, name, value):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")

    def fake_agent(self, agent, prompt, index):
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

    def run_pipeline(self, agent=None, scripts=None):
        def default_script(name):
            if name == "bundle":
                self.write("app.ait", "test bundle")
        with patch.object(self.factory, "preflight"), patch.object(self.factory, "run_agent", side_effect=agent or self.fake_agent), patch.object(TossHarnessIntegration, "run_script", side_effect=scripts or default_script), contextlib.redirect_stdout(io.StringIO()):
            return self.factory.run_full_pipeline("test")

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

    def test_invalid_workflow(self):
        config = load_config(DEFAULT_CONFIG)
        config["workflows"]["default_pipeline"].pop()
        self.write("bad.json", config)
        with self.assertRaises(ValueError):
            load_config(self.project / "bad.json")

    def test_message_round_trip(self):
        original = TaskMessage(status=TaskStatus.NEEDS_FIX)
        self.assertEqual(TaskMessage.from_json(original.to_json()), original)

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
