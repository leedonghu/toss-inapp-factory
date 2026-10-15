from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional
import json
import uuid
from datetime import datetime, timezone

class TaskType(str, Enum):
    PLAN = "PLAN"                     # 기획 및 작업 분해
    IMPLEMENT = "IMPLEMENT"           # 코드 구현 및 테스트
    UI_REVIEW = "UI_REVIEW"           # UI/UX 및 웹뷰 규격 검증
    CROSS_REVIEW = "CROSS_REVIEW"     # 심사 가이드 및 보안 검토
    FIX_REQUEST = "FIX_REQUEST"       # 오류 수정 요청
    BUNDLE = "BUNDLE"                 # .ait 번들 패키징

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEEDS_FIX = "NEEDS_FIX"

@dataclass
class TaskMessage:
    """AI 간 주고받는 표준 작업 메시지 규격"""
    task_id: str = field(default_factory=lambda: f"TASK-{uuid.uuid4().hex[:8].upper()}")
    from_agent: str = "orchestrator"  # claude, codex, antigravity, orchestrator
    to_agent: str = "codex"
    task_type: TaskType = TaskType.IMPLEMENT
    status: TaskStatus = TaskStatus.PENDING
    title: str = ""
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    context_files: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)
    feedback_notes: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskMessage":
        data = json.loads(json_str)
        data["task_type"] = TaskType(data["task_type"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)
