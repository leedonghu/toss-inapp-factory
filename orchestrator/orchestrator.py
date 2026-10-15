"""Fail-closed mini-app pipeline. Run with python -m orchestrator.orchestrator."""
import argparse
import json
import sys
import uuid
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.process import CommandError, resolve_command, run_command
from orchestrator.task_schema import TaskMessage, TaskType, TaskStatus
from integrations.toss_harness import TossHarnessIntegration

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "agents.yaml"
ACTIONS = ["PLAN", "IMPLEMENT", "UI_REVIEW", "CROSS_REVIEW", "BUNDLE"]


def load_config(path):
    # JSON is a YAML 1.2 subset; no third-party YAML dependency is needed.
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    pipeline = config["workflows"]["default_pipeline"]
    if [step["action"] for step in pipeline] != ACTIONS:
        raise ValueError(f"Pipeline actions must be {ACTIONS}")
    timeout = config["factory"]["timeout_seconds"]
    if type(timeout) is not int or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive integer")
    for step in pipeline[:-1]:
        agent = config["agents"][step["agent"]]
        args = agent["exec_args"]
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError("exec_args must be a list of strings")
        if not isinstance(agent["cli_command"], str) or not agent["cli_command"]:
            raise ValueError("cli_command must be a nonempty string")
    return config


class TossAIFactoryOrchestrator:
    def __init__(self, project_dir=None, config_path=DEFAULT_CONFIG):
        self.config = load_config(config_path)
        workspace = Path(self.config["factory"]["workspace_dir"])
        if not workspace.is_absolute():
            workspace = ROOT / workspace
        self.project_dir = Path(project_dir).resolve() if project_dir else (workspace / "roulette").resolve()
        self.timeout = self.config["factory"]["timeout_seconds"]
        self.run_dir = None

    def preflight(self):
        commands = {self.config["agents"][s["agent"]]["cli_command"]
                    for s in self.config["workflows"]["default_pipeline"][:-1]}
        errors = []
        for command in sorted(commands | {"npm"}):
            try:
                resolve_command([command])
            except CommandError as exc:
                errors.append(str(exc))
        if errors:
            raise CommandError("Preflight failed:\n" + "\n".join(errors))

    def save_task(self, task, index):
        (self.run_dir / f"{index:02d}-{task.task_type.value}.json").write_text(task.to_json(), encoding="utf-8")

    def require_file(self, relative):
        path = (self.project_dir / relative).resolve()
        if not path.is_relative_to(self.project_dir):
            raise ValueError(f"Artifact outside project: {relative}")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty artifact: {relative}")
        return path

    def run_agent(self, agent_name, prompt, index):
        agent = self.config["agents"][agent_name]
        return run_command([agent["cli_command"], *agent["exec_args"]], self.project_dir,
                           self.timeout, input_text=prompt,
                           log_prefix=self.run_dir / f"{index:02d}-{agent_name}")

    def run_full_pipeline(self, app_idea):
        self.preflight()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir = self.project_dir / ".factory" / uuid.uuid4().hex
        self.run_dir.mkdir(parents=True)
        harness = TossHarnessIntegration(self.project_dir, self.timeout)
        common = ("Work only in this project. Do not deploy, publish or upload. "
                  "Use current official Apps in Toss documentation. ")
        for index, step in enumerate(self.config["workflows"]["default_pipeline"], 1):
            action = step["action"]
            task = TaskMessage(to_agent=step["agent"], task_type=TaskType(action),
                               status=TaskStatus.IN_PROGRESS, title=action)
            self.save_task(task, index)
            print(f"[AI Factory] {action}", flush=True)
            try:
                if action == "PLAN":
                    tasks_path = (self.run_dir / "tasks.json").relative_to(self.project_dir).as_posix()
                    self.run_agent(step["agent"], common +
                        f"Idea: {app_idea}\nRead and update PRD.md, preserving existing requirements. "
                        f'Write {tasks_path} as {{"tasks":[{{"title":"...","acceptance_criteria":["..."]}}]}}. '
                        "Include app implementation and tests.", index)
                    self.require_file("PRD.md")
                    data = json.loads(self.require_file(tasks_path).read_text(encoding="utf-8-sig"))
                    tasks = data.get("tasks") if isinstance(data, dict) else None
                    if not isinstance(tasks, list) or not tasks:
                        raise ValueError("tasks.json must contain a nonempty tasks array")
                    for entry in tasks:
                        if not isinstance(entry, dict) or not isinstance(entry.get("title"), str) or not entry["title"].strip():
                            raise ValueError("Every task requires a title")
                        criteria = entry.get("acceptance_criteria")
                        if not isinstance(criteria, list) or not criteria or not all(isinstance(c, str) and c.strip() for c in criteria):
                            raise ValueError("Every task requires acceptance_criteria strings")
                    task.output_artifacts = ["PRD.md", tasks_path]
                elif action == "IMPLEMENT":
                    self.run_agent(step["agent"], common +
                        f"Implement PRD.md and {tasks_path}. Create an Apps in Toss React/TS app if absent. "
                        "Preserve existing files. Install dependencies. Provide package.json scripts "
                        "build, typecheck, lint, test (non-watch), and bundle (ait build). "
                        "Implement browser SDK fallback and meaningful tests. Run all checks.", index)
                    harness.run_typecheck_and_lint()
                    harness.run_script("test")
                    harness.run_script("build")
                    task.output_artifacts = ["package.json"]
                elif action in ("UI_REVIEW", "CROSS_REVIEW"):
                    report = (self.run_dir / f"{action}.json").relative_to(self.project_dir).as_posix()
                    scope = ("Mobile safe areas, touch behavior, accessibility and UI; do not claim "
                             "device testing unless performed." if action == "UI_REVIEW" else
                             "Architecture, privacy, external links, payments and submission requirements.")
                    self.run_agent(step["agent"], common + scope +
                        f' Read PRD.md and inspect implementation. Write {report} as '
                        '{"passed":true,"findings":[],"checks":["evidence of checks performed"]}. '
                        "Set passed=false for blocking or unverified requirements. Do not modify app code.", index)
                    result = json.loads(self.require_file(report).read_text(encoding="utf-8-sig"))
                    if not isinstance(result, dict) or type(result.get("passed")) is not bool:
                        raise ValueError("Review requires a boolean passed field")
                    if (not isinstance(result.get("findings"), list)
                            or not isinstance(result.get("checks"), list) or not result["checks"]
                            or not all(isinstance(c, str) and c.strip() for c in result["checks"])):
                        raise ValueError("Review requires findings and nonempty checks arrays")
                    task.output_artifacts = [report]
                    if not result["passed"]:
                        task.status = TaskStatus.NEEDS_FIX
                        raise ValueError(f"{action} rejected: {result['findings']}")
                else:
                    harness.run_typecheck_and_lint()
                    harness.run_script("test")
                    harness.run_script("build")
                    task.output_artifacts = [harness.build_ait_bundle()]
                task.status = TaskStatus.SUCCESS
            except (CommandError, ValueError, OSError, TypeError, KeyError) as exc:
                if task.status != TaskStatus.NEEDS_FIX:
                    task.status = TaskStatus.FAILED
                task.feedback_notes = str(exc)
                self.save_task(task, index)
                raise
            self.save_task(task, index)
        print(f"Ready for human review; not published. Records: {self.run_dir}")
        return task


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", nargs="?")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--idea", default="점심 메뉴 및 일상 선택을 도와주는 룰렛 토스 미니앱")
    parser.add_argument("--check", action="store_true", help="Check configuration and executables only")
    args = parser.parse_args(argv)
    try:
        factory = TossAIFactoryOrchestrator(args.project_dir, args.config)
        if args.check:
            factory.preflight()
            print(f"Preflight OK: {factory.project_dir}")
        else:
            factory.run_full_pipeline(args.idea)
        return 0
    except (CommandError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"[AI Factory] FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
