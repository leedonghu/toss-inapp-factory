"""파이프라인 단계마다 주고받고 기록하는 작업 메시지(TaskMessage)의 스키마 정의."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional
import json
import uuid
from datetime import datetime, timezone

class TaskType(str, Enum):
    """작업 종류. 값은 configs/agents.yaml의 파이프라인 action 이름과 일치한다."""
    PLAN = "PLAN"                     # 기획 및 작업 분해
    IMPLEMENT = "IMPLEMENT"           # 코드 구현 및 테스트
    LOGO = "LOGO"
    UI_REVIEW = "UI_REVIEW"           # UI/UX 및 웹뷰 규격 검증
    CROSS_REVIEW = "CROSS_REVIEW"     # 심사 가이드 및 보안 검토
    FIX_REQUEST = "FIX_REQUEST"       # 오류 수정 요청
    BUNDLE = "BUNDLE"                 # .ait 번들 패키징

class TaskStatus(str, Enum):
    """작업 진행 상태."""
    PENDING = "PENDING"           # 생성됨, 아직 시작 전
    IN_PROGRESS = "IN_PROGRESS"   # 실행 중
    SUCCESS = "SUCCESS"           # 성공 (산출물 검증 통과)
    FAILED = "FAILED"             # 명령 실패 또는 산출물 검증 실패
    NEEDS_FIX = "NEEDS_FIX"       # 리뷰 단계에서 반려됨 (수정 필요)

@dataclass
class TaskMessage:
    """AI 간 주고받는 표준 작업 메시지 규격"""
    # 작업 고유 ID (예: TASK-1A2B3C4D)
    task_id: str = field(default_factory=lambda: f"TASK-{uuid.uuid4().hex[:8].upper()}")
    from_agent: str = "orchestrator"  # claude, codex, antigravity, orchestrator
    to_agent: str = "codex"           # 작업을 수행할 에이전트 (BUNDLE은 "system")
    task_type: TaskType = TaskType.IMPLEMENT
    status: TaskStatus = TaskStatus.PENDING
    title: str = ""
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)  # 완료 판정 기준
    context_files: List[str] = field(default_factory=list)        # 참고할 입력 파일
    output_artifacts: List[str] = field(default_factory=list)     # 생성·검증된 산출물 경로
    feedback_notes: Optional[str] = None                          # 실패/반려 사유
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        """사람이 읽기 쉬운 JSON 문자열로 직렬화한다 (한글은 이스케이프하지 않음)."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskMessage":
        """to_json() 결과를 다시 TaskMessage로 복원한다. 문자열 enum 값은 Enum으로 되돌린다."""
        data = json.loads(json_str)
        data["task_type"] = TaskType(data["task_type"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)
