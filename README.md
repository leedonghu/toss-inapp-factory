# Toss MiniApp AI Factory

토스 미니앱의 기획 → 구현 → UI 검토 → 교차 검토 → 번들 검증을 연결하는 Python CLI입니다.
현재 저장소는 자동화 엔진과 룰렛 PRD를 포함합니다. 룰렛 앱 소스는 아직 생성되지 않았습니다.

## 실행 환경

- Python 3.10 이상. Python 외부 패키지 설치는 필요하지 않습니다.
- Node.js 및 npm
- 설정한 AI CLI 설치와 로그인, 해당 프로젝트에 필요한 파일 쓰기 권한
- 실제 미니앱 생성 시 사용할 Apps in Toss 개발 환경

`python`이 Windows 실행 별칭 오류를 내면 설치된 Python 실행 파일의 전체 경로를 사용하세요.
현재 개발 환경의 Codex 내장 Python으로 엔진 테스트를 실행했습니다.

```powershell
python -m orchestrator.orchestrator --check
python -m unittest discover -s tests -v
python -m orchestrator.orchestrator projects/roulette --idea "점심 메뉴 선택 룰렛"
```

직접 파일 실행도 지원합니다: `python orchestrator/orchestrator.py --check`.
`--check`는 설정과 실행 파일 경로만 확인하며 AI를 호출하거나 프로젝트를 생성하지 않습니다.
로그인, 권한, CLI의 실제 응답 규격까지 검증하는 옵션은 아닙니다.
일반 실행은 AI 사용량을 소비하고 지정 프로젝트의 파일 및 의존성을 변경합니다.
실패 시 종료 코드는 1이며 이후 단계를 실행하지 않습니다.

## 설정

`configs/agents.yaml`은 **JSON 문법으로 작성한 YAML 1.2 부분집합**입니다.
표준 라이브러리 JSON 파서를 사용하므로 JSON 문법을 유지하세요. YAML 주석/들여쓰기 문법은 지원하지 않습니다.
`--config <파일>`로 다른 설정을 지정할 수 있습니다.

- `workspace_dir`: 저장소 루트 기준 상대 경로 또는 절대 경로. 기본 프로젝트는 그 아래 `roulette`입니다.
- `timeout_seconds`: 명령 하나의 제한 시간. 기본 900초.
- `cli_command`, `exec_args`: 실행 파일과 고정 인자. 프롬프트는 UTF-8 stdin으로 전달합니다.
- 워크플로는 PLAN, IMPLEMENT, UI_REVIEW, CROSS_REVIEW, BUNDLE 순서를 검증합니다.
- 단계별 `agent`를 바꾸면 해당 설정의 CLI를 사용합니다.

기본 설정의 `agy`는 이 PC에서 발견되지 않았습니다. Antigravity의 headless CLI와 stdin 지원도 확인되지 않았으므로 예시 설정으로 취급하세요.
사용 가능한 CLI로 `UI_REVIEW`의 `agent`를 변경하거나, 검증된 실행 파일과 인자를 설정해야 전체 실행이 가능합니다.
권한을 우회하는 옵션은 사용하지 않습니다. 권한이나 네트워크 제한으로 작업을 수행하지 못하면 실패로 중단합니다.
Windows npm/npx는 npm의 Node 진입점을 직접 실행합니다. 다른 `.cmd`/`.bat` 래퍼는 자동 실행하지 않으며 네이티브 실행 파일 또는 Node 어댑터를 설정해야 합니다.

## 단계별 완료 조건

| 단계 | 완료 조건 |
|---|---|
| PLAN | 비어 있지 않은 PRD.md와 이번 실행의 유효한 tasks.json |
| IMPLEMENT | CLI 성공 + typecheck, lint, test, build 스크립트 성공 |
| UI_REVIEW | 이번 실행의 JSON 리뷰에서 passed가 boolean true이고 checks가 존재 |
| CROSS_REVIEW | 별도의 JSON 리뷰 통과 |
| BUNDLE | 검증 스크립트 재실행 + bundle 성공 + 새로 생성/갱신된 비어 있지 않은 .ait 파일 |

미니앱의 `package.json`에는 `typecheck`, `lint`, `test`, `build`, `bundle` 스크립트가 필요합니다.
`test`는 watch 모드를 사용하지 않아야 합니다. `bundle`은 실제 `ait build`를 수행하도록 구성합니다.
엔진은 AI가 빌드 성공을 주장하는 것만으로 통과시키지 않고 명령을 직접 실행합니다.
단, 스크립트 자체의 품질과 AI 리뷰 정확성은 사람이 확인해야 합니다.

실행 기록은 `<프로젝트>/.factory/<run-id>/`에 저장됩니다.
각 단계의 상태 JSON, 에이전트 stdout/stderr, 작업 목록, 리뷰 결과가 포함됩니다.
이전 실행의 작업 목록/리뷰를 재사용하지 않습니다.
검토 탈락은 `NEEDS_FIX`, 명령/검증 오류는 `FAILED`로 기록합니다.
실패 이유를 수정한 뒤 재실행하세요. 자동 수정 반복이나 중간 단계 재개는 아직 지원하지 않습니다.

완료는 **사람이 확인할 번들 준비 완료**를 의미합니다. 업로드, 심사 제출, 출시는 구현하지 않았습니다.
기기별 실측 QA와 심사 통과를 보장하지 않습니다.

## 구조

```text
toss-app-factory/
  configs/agents.yaml
  orchestrator/
    orchestrator.py    # 설정, 사전 점검, 단계 실행 및 검증
    process.py         # 셸을 거치지 않는 명령 실행
    task_schema.py     # 작업 상태 및 JSON 직렬화
  integrations/toss_harness.py
  projects/roulette/PRD.md
  tests/test_factory.py
```

`init_miniapp_template()`는 빈 대상 경로에서 `create-ait-app`을 호출하는 독립 유틸리티입니다.
기존 PRD를 덮어쓰지 않도록 기본 파이프라인은 이 함수를 자동 호출하지 않고 구현 에이전트가 기존 파일을 보존하여 초기화하도록 지시합니다.

## 확인한 공식 자료

- [Codex 비대화형 실행](https://developers.openai.com/codex/noninteractive)
- [Apps in Toss Harness](https://github.com/toss/apps-in-toss-harness)
- [앱인토스 개발자센터](https://developers-apps-in-toss.toss.im/)

CLI 명령과 SDK 규격은 업데이트될 수 있으므로 실제 앱 생성 시 공식 문서를 다시 확인하세요.
