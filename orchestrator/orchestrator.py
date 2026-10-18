"""Fail-closed mini-app pipeline. Run with python -m orchestrator.orchestrator."""
# 여러 AI 에이전트(claude, codex, antigravity)를 순서대로 호출해 토스 미니앱을
# 기획 → 구현 → UI 리뷰 → 교차 리뷰 → 번들링까지 만드는 파이프라인.
# "Fail-closed": 어떤 단계든 명령 실패나 산출물 검증 실패가 있으면 즉시 중단하고,
# 다음 단계로 넘어가지 않는다. 배포/업로드는 하지 않고 사람 검토 직전에서 멈춘다.
import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

# `python orchestrator/orchestrator.py`처럼 스크립트로 직접 실행한 경우에도
# orchestrator / integrations 패키지를 import할 수 있도록 저장소 루트를 경로에 추가한다.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.process import CommandError, resolve_command, run_command
from orchestrator.task_schema import TaskMessage, TaskType, TaskStatus
from integrations.toss_harness import TossHarnessIntegration

ROOT = Path(__file__).resolve().parents[1]                 # 저장소 루트
DEFAULT_CONFIG = ROOT / "configs" / "agents.yaml"
# 파이프라인은 반드시 이 순서의 단계로 구성되어야 한다 (설정 파일로 순서를 바꿀 수 없음).
ACTIONS = ["PLAN", "IMPLEMENT", "UI_REVIEW", "CROSS_REVIEW", "BUNDLE"]
# 하네스가 직접 실행해 결과를 보장하는 npm 검사 (리뷰어는 이 로그를 근거로 삼는다).
CHECK_SCRIPTS = ["typecheck", "lint", "test", "build"]


def load_config(path):
    """설정 파일을 읽고 형식을 검증한다. 잘못되면 ValueError/KeyError."""
    # JSON is a YAML 1.2 subset; no third-party YAML dependency is needed.
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    pipeline = config["workflows"]["default_pipeline"]
    if [step["action"] for step in pipeline] != ACTIONS:
        raise ValueError(f"Pipeline actions must be {ACTIONS}")
    timeout = config["factory"]["timeout_seconds"]
    # bool은 int의 하위 타입이라 isinstance로는 True가 통과하므로 type()으로 정확히 검사한다.
    if type(timeout) is not int or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive integer")
    # 마지막 BUNDLE 단계는 에이전트가 아닌 시스템이 수행하므로 검증에서 제외한다.
    for step in pipeline[:-1]:
        agent = config["agents"][step["agent"]]
        args = agent["exec_args"]
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError("exec_args must be a list of strings")
        if not isinstance(agent["cli_command"], str) or not agent["cli_command"]:
            raise ValueError("cli_command must be a nonempty string")
    return config


class TossAIFactoryOrchestrator:
    """설정에 정의된 파이프라인을 실행하고, 단계별 결과를 .factory/<run id>/에 기록한다."""

    def __init__(self, project_dir=None, config_path=DEFAULT_CONFIG):
        self.config = load_config(config_path)
        workspace = Path(self.config["factory"]["workspace_dir"])
        if not workspace.is_absolute():
            workspace = ROOT / workspace
        # 프로젝트 경로를 지정하지 않으면 기본 파일럿 앱인 projects/roulette을 사용한다.
        self.project_dir = Path(project_dir).resolve() if project_dir else (workspace / "roulette").resolve()
        self.timeout = self.config["factory"]["timeout_seconds"]
        self.run_dir = None  # run_full_pipeline() 실행 시 생성되는 이번 실행의 기록 디렉터리

    def preflight(self):
        """파이프라인에 필요한 CLI(에이전트들 + npm)가 모두 실행 가능한지 미리 확인한다.

        누락된 항목을 한 번에 모두 보고하기 위해 오류를 모았다가 마지막에 던진다.
        """
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
        """단계 상태를 `NN-<단계>.json` 파일로 저장한다 (같은 단계는 덮어씀)."""
        (self.run_dir / f"{index:02d}-{task.task_type.value}.json").write_text(task.to_json(), encoding="utf-8")

    def require_file(self, relative):
        """에이전트가 만들어야 하는 산출물이 프로젝트 안에 비어 있지 않게 존재하는지 확인한다."""
        path = (self.project_dir / relative).resolve()
        # `../` 등으로 프로젝트 밖 파일을 가리키는 경로는 거부한다.
        if not path.is_relative_to(self.project_dir):
            raise ValueError(f"Artifact outside project: {relative}")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty artifact: {relative}")
        return path

    def project_files(self):
        """리뷰 에이전트가 쉘 명령 없이도 파일 목록을 알 수 있도록 프로젝트 내 주요 파일 경로를 반환한다."""
        ignored = {"node_modules", ".git", ".factory", "dist", ".npm-cache", "test-results"}
        files = [
            p.relative_to(self.project_dir).as_posix()
            for p in self.project_dir.rglob("*")
            if not any(part in ignored for part in p.relative_to(self.project_dir).parts)
            and p.is_file() and p.resolve().is_relative_to(self.project_dir)
        ]
        return sorted(files)[:80]

    def run_agent(self, agent_name, prompt, index):
        """에이전트 CLI를 실행한다. {prompt} 인자가 있으면 치환하고, 없으면 stdin을 사용한다.

        출력은 `NN-<에이전트>.stdout.log` / `.stderr.log`로 실행 기록 디렉터리에 남는다.
        """
        agent = self.config["agents"][agent_name]
        uses_prompt_arg = any("{prompt}" in arg for arg in agent["exec_args"])
        args = [arg.replace("{prompt}", prompt) for arg in agent["exec_args"]]
        output = run_command([agent["cli_command"], *args], self.project_dir,
                           self.timeout, input_text="" if uses_prompt_arg else prompt,
                           log_prefix=self.run_dir / f"{index:02d}-{agent_name}")
        # Some CLIs exit zero even when headless tool permissions blocked the work.
        try:
            envelope = json.loads(output)
        except (ValueError, TypeError):
            envelope = None
        if isinstance(envelope, dict) and envelope.get("denied_actions"):
            raise CommandError(
                f"{agent_name}: tool permissions denied: "
                f"{json.dumps(envelope['denied_actions'], ensure_ascii=False)}. "
                "Headless mode cannot request approval. Configure narrowly scoped CLI "
                "permissions or select another configured review agent, then --resume. "
                f"See {self.run_dir / f'{index:02d}-{agent_name}.stderr.log'}")
        return output

    def validate_plan(self, tasks_path):
        self.require_file("PRD.md")
        data = json.loads(self.require_file(tasks_path).read_text(encoding="utf-8-sig"))
        tasks = data.get("tasks") if isinstance(data, dict) else None
        if not isinstance(tasks, list) or not tasks:
            raise ValueError("tasks.json must contain a nonempty tasks array")
        # 모든 작업에 제목과 비어 있지 않은 완료 기준이 있어야 한다.
        for entry in tasks:
            if not isinstance(entry, dict) or not isinstance(entry.get("title"), str) or not entry["title"].strip():
                raise ValueError("Every task requires a title")
            criteria = entry.get("acceptance_criteria")
            if not isinstance(criteria, list) or not criteria or not all(isinstance(c, str) and c.strip() for c in criteria):
                raise ValueError("Every task requires acceptance_criteria strings")

    def read_review(self, report):
        """리뷰 보고서를 읽고 형식을 검증한다. passed 값과 관계없이 결과를 반환한다."""
        result = json.loads(self.require_file(report).read_text(encoding="utf-8-sig"))
        # "false" 같은 문자열이 truthy로 통과하지 않도록 passed는 진짜 bool이어야 한다.
        if not isinstance(result, dict) or type(result.get("passed")) is not bool:
            raise ValueError("Review requires a boolean passed field")
        # 실제로 무엇을 확인했는지(checks) 근거가 없으면 통과로 인정하지 않는다.
        if (not isinstance(result.get("findings"), list)
                or not isinstance(result.get("checks"), list) or not result["checks"]
                or not all(isinstance(c, str) and c.strip() for c in result["checks"])):
            raise ValueError("Review requires findings and nonempty checks arrays")
        # 사람만 할 수 있는 검증(실기기, 토스 테스트 빌드 등)은 차단 대신 manual_checks로 받는다.
        # 이 필드가 없던 예전 보고서도 재개할 수 있도록 생략은 허용한다.
        manual = result.setdefault("manual_checks", [])
        if not isinstance(manual, list) or not all(isinstance(c, str) and c.strip() for c in manual):
            raise ValueError("Review manual_checks must be an array of strings")
        return result

    def validate_review(self, report):
        result = self.read_review(report)
        if not result["passed"]:
            raise ValueError("Completed review is not passed")
        return result

    def run_checks(self, harness, index):
        """npm 검사를 순서대로 실행하고 출력을 `NN-npm-<스크립트>.*.log`로 남긴다."""
        harness.log_prefix = self.run_dir / f"{index:02d}-npm"
        for name in CHECK_SCRIPTS:
            harness.run_script(name)

    def check_logs(self):
        """리뷰어에게 알려줄 IMPLEMENT 단계 npm 로그 경로 (프로젝트 기준 상대 경로)."""
        return [p.relative_to(self.project_dir).as_posix()
                for p in sorted(self.run_dir.glob(f"{ACTIONS.index('IMPLEMENT') + 1:02d}-npm-*.log"))]

    def collect_manual_checks(self):
        """리뷰 보고서들의 manual_checks를 모아 manual_checks.json에 기록하고 반환한다."""
        manual = {}
        for action in ("UI_REVIEW", "CROSS_REVIEW"):
            report = (self.run_dir / f"{action}.json").relative_to(self.project_dir)
            manual[action] = self.read_review(report)["manual_checks"]
        (self.run_dir / "manual_checks.json").write_text(
            json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
        return manual

    def prepare_resume(self, run_id):
        """Validate a checkpoint without modifying it; only a contiguous success prefix is reused."""
        if not run_id or Path(run_id).name != run_id or run_id in (".", ".."):
            raise ValueError("--resume requires a run ID, not a path")
        source = (self.project_dir / ".factory" / run_id).resolve()
        if source.parent != self.project_dir / ".factory" or not source.is_dir():
            raise ValueError("Resume run must exist inside this project's .factory directory")
        completed = []
        for index, action in enumerate(ACTIONS, 1):
            path = source / f"{index:02d}-{action}.json"
            if not path.exists():
                break
            record = TaskMessage.from_json(path.read_text(encoding="utf-8-sig"))
            if record.task_type.value != action:
                raise ValueError(f"Invalid checkpoint stage: {path.name}")
            if record.status != TaskStatus.SUCCESS:
                break
            completed.append(record)
        if len(completed) == len(ACTIONS):
            raise ValueError("This run is already complete")
        if completed:
            self.validate_plan((source / "tasks.json").relative_to(self.project_dir))
        if len(completed) >= 2:
            self.require_file("package.json")
        for action in ACTIONS[2:len(completed)]:
            self.validate_review((source / f"{action}.json").relative_to(self.project_dir))
        return source, completed

    def run_full_pipeline(self, app_idea, resume=None):
        """앱 아이디어를 받아 전체 파이프라인을 실행하고, 마지막(BUNDLE) 단계의 TaskMessage를 반환한다.

        어느 단계든 실패하면 해당 단계를 FAILED(리뷰 반려는 NEEDS_FIX)로 기록하고 예외를 다시 던진다.
        """
        source, completed = self.prepare_resume(resume) if resume else (None, [])
        self.preflight()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        # 실행마다 새 디렉터리를 만들어, 이전 실행의 tasks.json/리뷰 보고서를 재사용하지 못하게 한다.
        self.run_dir = self.project_dir / ".factory" / uuid.uuid4().hex
        self.run_dir.mkdir(parents=True)
        tasks_path = (self.run_dir / "tasks.json").relative_to(self.project_dir).as_posix()
        if source:
            # New attempt directory preserves failed logs and prevents stale retry reports passing.
            (self.run_dir / "resume.json").write_text(json.dumps({
                "source_run": source.name, "start_stage": ACTIONS[len(completed)]
            }), encoding="utf-8")
            for index, record in enumerate(completed, 1):
                action = record.task_type.value
                if action == "PLAN":
                    shutil.copyfile(self.require_file((source / "tasks.json").relative_to(self.project_dir)), self.run_dir / "tasks.json")
                    record.output_artifacts = ["PRD.md", tasks_path]
                elif action in ("UI_REVIEW", "CROSS_REVIEW"):
                    shutil.copyfile(self.require_file((source / f"{action}.json").relative_to(self.project_dir)), self.run_dir / f"{action}.json")
                    record.output_artifacts = [(self.run_dir / f"{action}.json").relative_to(self.project_dir).as_posix()]
                self.save_task(record, index)
            print(f"[AI Factory] Resuming {source.name} from {ACTIONS[len(completed)]}", flush=True)
        harness = TossHarnessIntegration(self.project_dir, self.timeout)
        if len(completed) >= ACTIONS.index("IMPLEMENT") + 1:
            # 재개 전에 코드가 바뀌었을 수 있으니 IMPLEMENT 검사를 다시 돌려 확인하고,
            # 이번 실행 디렉터리에 리뷰어가 볼 npm 로그를 새로 남긴다.
            print("[AI Factory] Re-running IMPLEMENT checks", flush=True)
            self.run_checks(harness, ACTIONS.index("IMPLEMENT") + 1)
        # 모든 에이전트 프롬프트 앞에 붙는 공통 제약 사항.
        common = ("Work only in this project. Do not deploy, publish or upload. "
                  "Use current official Apps in Toss documentation. ")
        for index, step in enumerate(self.config["workflows"]["default_pipeline"], 1):
            if index <= len(completed):
                continue
            action = step["action"]
            task = TaskMessage(to_agent=step["agent"], task_type=TaskType(action),
                               status=TaskStatus.IN_PROGRESS, title=action)
            # 시작 시점에도 기록해 두면, 중간에 프로세스가 죽어도 어느 단계였는지 남는다.
            self.save_task(task, index)
            print(f"[AI Factory] {action}", flush=True)
            try:
                if action == "PLAN":
                    # 1) 기획: PRD.md를 갱신하고, 작업 목록(tasks.json)을 이번 실행 디렉터리에 작성.
                    tasks_path = (self.run_dir / "tasks.json").relative_to(self.project_dir).as_posix()
                    self.run_agent(step["agent"], common +
                        f"Idea: {app_idea}\nRead and update PRD.md, preserving existing requirements. "
                        f'Write {tasks_path} as {{"tasks":[{{"title":"...","acceptance_criteria":["..."]}}]}}. '
                        "Include app implementation and tests.", index)
                    # 에이전트의 "완료했다"는 말을 믿지 않고, 산출물을 직접 검증한다.
                    self.validate_plan(tasks_path)
                    task.output_artifacts = ["PRD.md", tasks_path]
                elif action == "IMPLEMENT":
                    # 2) 구현: 앱 코드와 필수 npm 스크립트를 만들게 한 뒤, 하네스가 직접 검사를 돌린다.
                    #    (tasks_path는 PLAN 단계에서 설정된 값. 파이프라인 순서가 고정이라 항상 존재)
                    self.run_agent(step["agent"], common +
                        f"Implement PRD.md and {tasks_path}. Create an Apps in Toss React/TS app if absent. "
                        "Preserve existing files. Install dependencies. Provide package.json scripts "
                        "build, typecheck, lint, test (non-watch), and bundle (producing a nonempty .ait file via ait build). "
                        "Implement browser SDK fallback and meaningful tests. Run all checks including bundle.", index)
                    self.run_checks(harness, index)
                    task.output_artifacts = ["package.json"]
                elif action in ("UI_REVIEW", "CROSS_REVIEW"):
                    # 3), 4) 리뷰: 코드 수정 없이 검토만 하고, 결과를 JSON 보고서로 작성하게 한다.
                    report = (self.run_dir / f"{action}.json").relative_to(self.project_dir).as_posix()
                    scope = ("Mobile safe areas, touch behavior, accessibility and UI; do not claim "
                             "device testing unless performed." if action == "UI_REVIEW" else
                             "Architecture, privacy, external links, payments and submission requirements.")
                    files = self.project_files()
                    files_hint = f" Project files: {', '.join(files)}." if files else ""
                    logs = self.check_logs()
                    logs_hint = (f" The factory ran npm run {', '.join(CHECK_SCRIPTS)} itself and all exited 0; "
                                 f"their output is in {', '.join(logs)}. Use these logs as evidence instead of "
                                 "running the commands." if logs else "")
                    self.run_agent(step["agent"], common + scope + files_hint + logs_hint +
                        " Do not run shell or terminal commands (never call run_command); use only file read/write tools "
                        "(view_file and write_to_file)."
                        f' Read PRD.md and inspect implementation files directly. Write {report} as '
                        '{"passed":true,"findings":[],"checks":["evidence of checks performed"],'
                        '"manual_checks":["verification only a human can do"]}. '
                        "Set passed=false only for blocking problems you can confirm from code, config, docs or the logs. "
                        "Verification that needs a human, a real device or browser, a Toss app test build, or the "
                        "developer console goes in manual_checks instead and does not by itself make passed false; "
                        "never claim it was done. Do not modify app code.", index)
                    result = self.read_review(report)
                    task.output_artifacts = [report]
                    if not result["passed"]:
                        # 반려는 일반 실패와 구분해 NEEDS_FIX로 기록한다 (아래 except에서 유지됨).
                        task.status = TaskStatus.NEEDS_FIX
                        raise ValueError(f"{action} rejected: {result['findings']}")
                else:
                    # 5) BUNDLE: 리뷰 이후 코드가 바뀌었을 수 있으므로 모든 검사를 다시 돌린 뒤 .ait 번들 생성.
                    self.run_checks(harness, index)
                    task.output_artifacts = [harness.build_ait_bundle()]
                task.status = TaskStatus.SUCCESS
            except (CommandError, ValueError, OSError, TypeError, KeyError) as exc:
                # 실패 사유를 기록으로 남긴 뒤 예외를 그대로 올려 파이프라인을 중단한다.
                if task.status != TaskStatus.NEEDS_FIX:
                    task.status = TaskStatus.FAILED
                task.feedback_notes = str(exc)
                self.save_task(task, index)
                raise
            self.save_task(task, index)
        manual = self.collect_manual_checks()
        for action, checks in manual.items():
            for check in checks:
                print(f"[Manual check] {action}: {check}")
        print(f"Ready for human review; not published. Records: {self.run_dir}")
        return task


def main(argv=None):
    """CLI 진입점. 성공하면 0, 실패하면 오류를 stderr에 출력하고 1을 반환한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", nargs="?")  # 생략하면 projects/roulette
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--idea", default="점심 메뉴 및 일상 선택을 도와주는 룰렛 토스 미니앱")
    parser.add_argument("--check", action="store_true", help="Check configuration and executables only")
    parser.add_argument("--resume", metavar="RUN_ID", help="Resume the first incomplete stage of an existing run")
    args = parser.parse_args(argv)
    try:
        factory = TossAIFactoryOrchestrator(args.project_dir, args.config)
        if args.check:
            # --check는 설정과 CLI 존재 여부만 확인하고, 프로젝트 디렉터리는 만들지 않는다.
            factory.preflight()
            print(f"Preflight OK: {factory.project_dir}")
        else:
            factory.run_full_pipeline(args.idea, resume=args.resume)
        return 0
    except (CommandError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"[AI Factory] FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
