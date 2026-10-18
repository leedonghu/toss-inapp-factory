"""Human-readable work reports derived from stage records and original CLI logs."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROLES = {
    "PLAN": "기획서 보완 및 완료 기준이 있는 작업 목록 작성",
    "IMPLEMENT": "앱 코드·테스트 구현 및 빌드 검증",
    "UI_REVIEW": "모바일 화면·터치·접근성 검토",
    "CROSS_REVIEW": "구조·권한·개인정보·제출 요건 교차 검토",
    "BUNDLE": "시스템의 타입 검사·린트·테스트·빌드 및 번들 검증",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def origin(run_dir, filename, task_id):
    """Follow copied task IDs back to their original attempt, including legacy runs."""
    current = run_dir
    seen = set()
    while current.name not in seen:
        seen.add(current.name)
        resume = current / "resume.json"
        if not resume.is_file():
            break
        parent = (run_dir.parent / read_json(resume)["source_run"]).resolve()
        if parent.parent != run_dir.parent.resolve() or not (parent / filename).is_file():
            break
        if read_json(parent / filename).get("task_id") != task_id:
            break
        current = parent
    return current


def record_event(run_dir, task, index):
    event = {"time": datetime.now(timezone.utc).isoformat(), "stage": task.task_type.value,
             "index": index, "agent": task.to_agent, "status": task.status.value,
             "task_id": task.task_id, "artifacts": task.output_artifacts,
             "error": task.feedback_notes}
    filename = f"{index:02d}-{task.task_type.value}.json"
    source = origin(run_dir, filename, task.task_id)
    event["mode"] = "reused" if source != run_dir else "executed"
    event["source_run"] = source.name
    with (run_dir / "activity.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def record_check(run_dir, index, name, status, error=None):
    event = {"time": datetime.now(timezone.utc).isoformat(), "agent": "system",
             "stage": "SYSTEM_CHECK", "index": index, "command": f"npm run {name}",
             "status": status, "error": error}
    with (run_dir / "activity.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_report(run_dir):
    run_dir = Path(run_dir).resolve()
    lines = ["# AI 작업 기록", "", f"실행 ID: `{run_dir.name}`", "",
             "단계 상태는 엔진 기록이며, 아래 AI 응답은 자기 보고입니다. 실기기 검증을 의미하지 않습니다.",
             "재사용 단계는 원본 실행을 표시합니다. 과거 실행의 시각·이벤트는 추정해서 만들지 않습니다.", ""]
    for index, (action, role) in enumerate(ROLES.items(), 1):
        filename = f"{index:02d}-{action}.json"
        path = run_dir / filename
        lines.extend([f"## {index}. {action} — {role}", ""])
        if not path.is_file():
            lines.extend(["상태: 미실행", ""])
            continue
        task = read_json(path)
        source = origin(run_dir, filename, task["task_id"])
        agent = task["to_agent"]
        mode = "이전 실행 결과 재사용" if source != run_dir else "이번 실행"
        lines.extend([f"담당: `{agent}` · 상태: `{task['status']}` · {mode}",
                      f"원본 실행: `{source.name}` · 원본 단계 시작: `{task.get('created_at', '알 수 없음')}`", ""])
        for artifact in task.get("output_artifacts", []):
            lines.append(f"- 산출물: `{artifact}`")
        if task.get("feedback_notes"):
            lines.extend(["", "오류 / 수정 요청:", *["> " + x for x in task["feedback_notes"].splitlines()]])
        for kind in ("prompt.txt", "stdout.log", "stderr.log"):
            log = source / f"{index:02d}-{agent}.{kind}"
            if log.is_file():
                relative = f"../{source.name}/{log.name}"
                lines.append(f"- [{kind}]({relative})")
        log = source / f"{index:02d}-{agent}.stdout.log"
        if log.is_file():
            response = log.read_text(encoding="utf-8-sig", errors="replace").strip()
            try:
                envelope = json.loads(response)
                if isinstance(envelope, dict) and isinstance(envelope.get("response"), str):
                    response = envelope["response"]
            except ValueError:
                pass
            if response:
                lines.extend(["", "AI가 보고한 작업 내용 (최대 12,000자, 전체 내용은 stdout.log):", "",
                              *["> " + x for x in response[:12000].splitlines()]])
        report = run_dir / f"{action}.json"
        if report.is_file():
            try:
                review = read_json(report)
                if not isinstance(review, dict):
                    raise ValueError("Not an object")
            except (ValueError, OSError):
                lines.extend(["", "리뷰 JSON이 유효하지 않습니다. 원본 파일을 확인하세요.", ""])
                continue
            for key, label in (("checks", "검토 근거 (AI 보고)"), ("findings", "발견 사항"),
                               ("manual_checks", "사람이 확인할 항목")):
                lines.extend(["", f"### {label}", ""])
                items = review.get(key, [])
                for item in items if isinstance(items, list) else [items]:
                    value = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
                    lines.append("- " + value.replace("\n", " "))
        lines.append("")
    lines.extend(["## 이번 실행의 시스템 검사 로그", "",
                  "재개 실행에서는 AI 구현을 재사용하더라도 시스템 검사를 다시 수행할 수 있습니다.", ""])
    lines.extend(f"- [{p.name}]({p.name})" for p in sorted(run_dir.glob("*-npm-*.log")))
    events = run_dir / "activity.jsonl"
    if events.is_file():
        lines.extend(["", "### 시스템 검사 실행 이력", ""])
        for line in events.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("stage") == "SYSTEM_CHECK":
                lines.append(f"- {event['time']} · {event['command']} · {event['status']}")
                if event.get("error"):
                    lines.extend("> " + x for x in event["error"].splitlines())
    target = run_dir / "WORK_LOG.md"
    temp = target.with_suffix(".md.tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp.replace(target)
    return target
