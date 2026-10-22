# Toss MiniApp AI Factory

토스 미니앱의 기획 → 구현 → 로고 제작 → UI 검토 → 교차 검토 → 번들 검증을 연결하는 Python CLI입니다.
현재 저장소는 자동화 엔진과 룰렛 앱 프로젝트를 포함합니다.

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
- `timeout_seconds`: 명령 하나의 제한 시간. 기본 1800초.
- `cli_command`, `exec_args`: 실행 파일과 인자. `{prompt}`가 있으면 해당 인자에 프롬프트를 치환하고, 없으면 UTF-8 stdin으로 전달합니다. 인자는 셸을 거치지 않고 전달합니다.
- 워크플로는 PLAN, IMPLEMENT, LOGO, UI_REVIEW, CROSS_REVIEW, BUNDLE 순서를 검증합니다.
- 단계별 `agent`를 바꾸면 해당 설정의 CLI를 사용합니다.

기본 설정은 각 CLI의 비대화형 실행 규격에 맞춰 구성되어 있습니다:
- `claude`: `-p --permission-mode acceptEdits` (비대화형 프롬프트 및 프로젝트 내 파일 편집 허용)
- `codex`: `exec --sandbox workspace-write -c sandbox_workspace_write.network_access=true --skip-git-repo-check -` (워크스페이스 쓰기 샌드박스 유지 및 `npm install`용 네트워크 허용)
- `antigravity` (`agy`): `--mode accept-edits --output-format json -p={prompt}` (프롬프트를 `-p=`에 붙여 전달하며, 리뷰 리포트 파일 작성 허용)
권한 전체를 우회하는 위험 옵션(`--dangerously-*`)은 사용하지 않습니다. 권한이나 네트워크 제한으로 작업을 수행하지 못하면 실패로 중단합니다.
Windows npm/npx는 npm의 Node 진입점을 직접 실행합니다. 다른 `.cmd`/`.bat` 래퍼는 자동 실행하지 않으며 네이티브 실행 파일 또는 Node 어댑터를 설정해야 합니다.

## 단계별 완료 조건

| 단계 | 완료 조건 |
|---|---|
| PLAN | 비어 있지 않은 PRD.md와 이번 실행의 유효한 tasks.json |
| IMPLEMENT | CLI 성공 + typecheck, lint, test, build 스크립트 성공 |
| LOGO | 600×600 불투명 RGB PNG + LOGO.md + 이번 실행의 통과 보고서 및 PNG SHA-256 일치 |
| UI_REVIEW | 이번 실행의 JSON 리뷰에서 passed가 boolean true이고 checks가 존재 |
| CROSS_REVIEW | 별도의 JSON 리뷰 통과 |
| BUNDLE | 검증 스크립트 재실행 + bundle 성공 + 새로 생성/갱신된 비어 있지 않은 .ait 파일 |

### 로고 제작 및 검토

`IMPLEMENT` 다음에 Codex가 `LOGO` 단계를 수행합니다. PRD의 서비스 특성을 바탕으로 독창적인 로고를 만들고 앱의 로컬 아이콘 참조에 반영합니다.

- `public/logo-600x600.png`: 정확히 600 × 600px 정사각형. 배경색이 전체를 채우며 둥근 외곽 모서리·둥근 사각 프레임·투명 배경은 금지합니다. 자동 검사를 위해 **8-bit RGB, 비인터레이스 PNG**로 내보냅니다. RGBA 파일은 완전히 불투명하더라도 RGB로 변환해야 합니다.
- 작은 크기(24/32/48px)에서도 선명하고 서비스 특성이 드러나는 단순한 형태를 사용하며 밝은 배경과 다크 모드 배경에서 실제 이미지를 확인합니다.
- 다른 앱·브랜드·캐릭터를 모방하지 않습니다. 토스 제공 아이콘·이미지 및 2차 가공물, 사람 얼굴(실제처럼 보이는 AI 얼굴 포함)은 사용하지 않습니다.
- 편집 가능한 원본과 `LOGO.md`에 콘셉트·색상·제작 방식·리소스 출처와 이용 조건·유사 로고 비교·실제 시각 검토 근거를 기록합니다.
- 이미지 생성 도구가 없으면 직접 설계한 기하학 벡터를 PNG로 렌더링합니다. 렌더링이나 이미지 확인을 수행할 수 없으면 임시 이미지로 통과시키지 않고 실패합니다.

엔진은 PNG 구조·체크섬·픽셀 스트림·크기·불투명 형식을 직접 검사하며, `.factory/<run-id>/LOGO.json`의 SHA-256으로 검토한 파일과 현재 파일이 같은지 확인합니다. 재개 시와 번들 생성 전후에도 다시 검사합니다. 디자인 적합성은 제작 근거와 UI·교차 검토로 확인하며, 자동 검사가 저작권이나 상표 비침해를 보장하지는 않습니다. 제출 전 권리·유사성 최종 확인은 사람의 검토 항목으로 남깁니다.

로고는 번들과 함께 전달할 산출물이며 콘솔 업로드는 자동 수행하지 않습니다. 새 단계가 없던 과거 실행을 재개하면 PLAN/IMPLEMENT까지만 재사용하고 LOGO부터 실행하여 후속 리뷰를 새로 받습니다. 커스텀 설정에도 LOGO 단계를 추가해야 합니다.

미니앱의 `package.json`에는 `typecheck`, `lint`, `test`, `build`, `bundle` 스크립트가 필요합니다.
`test`는 watch 모드를 사용하지 않아야 합니다. `bundle`은 실제 `ait build`를 수행하도록 구성합니다.
엔진은 AI가 빌드 성공을 주장하는 것만으로 통과시키지 않고 명령을 직접 실행합니다.
단, 스크립트 자체의 품질과 AI 리뷰 정확성은 사람이 확인해야 합니다.

실행 기록은 `<프로젝트>/.factory/<run-id>/`에 저장됩니다.
각 단계의 상태 JSON, 에이전트 stdout/stderr, 작업 목록, 리뷰 결과가 포함됩니다.

### AI별 작업 기록

실행 중 단계가 시작·완료·실패할 때 다음 기록을 자동으로 갱신합니다.

- `WORK_LOG.md`: 담당 AI, 역할, 단계 상태, 원본 실행, 산출물, AI 응답, 리뷰 근거·지적 사항·수동 확인 항목과 시스템 검사 로그를 모은 작업 요약.
- `activity.jsonl`: 단계 상태 변경 및 시스템 검사 시작·성공·실패의 UTC 시각을 한 줄씩 추가하는 이벤트 기록.
- `NN-<agent>.prompt.txt`: AI에게 실제 전달한 작업 지시문. stdout/stderr 원본도 별도로 보존됩니다.

재개 시 복사된 SUCCESS는 **이전 실행 결과 재사용**으로 표시하고 원본 실행의 응답을 연결합니다. AI가 보고한 작업과 엔진의 검증 상태를 구분하며, AI 응답은 파일별 변경 내역을 완전히 증명하는 감사 로그가 아닙니다. 지시문과 출력이 저장되므로 공유 전 민감한 내용이 없는지 확인하세요.

기존 실행도 AI 호출 없이 요약을 만들 수 있습니다(기존 단계 기록은 변경하지 않습니다).

```powershell
python -m orchestrator.orchestrator projects/roulette --report <실행 ID>
```

과거 실행에 없던 프롬프트·이벤트·시간은 소급 생성하지 않습니다. `WORK_LOG.md`는 단계별 최신 요약이며 상세 상태 전이는 `activity.jsonl`에서 확인할 수 있습니다.
새 실행은 이전 실행의 작업 목록/리뷰를 재사용하지 않습니다. `--resume`에서는 완료된 단계의 검증된 작업 목록/리뷰만 복사합니다.
검토 탈락은 `NEEDS_FIX`, 명령/검증 오류는 `FAILED`로 기록합니다.
실패 이유를 수정한 뒤 `--resume <실행 ID>`로 첫 미완료 단계부터 재개할 수 있습니다.

```powershell
python -m orchestrator.orchestrator projects/roulette --resume <실행 ID>
```

실행 ID는 `projects/roulette/.factory/` 아래 폴더 이름입니다. 연속된 SUCCESS 단계를 건너뛰고 FAILED, NEEDS_FIX, IN_PROGRESS 또는 기록이 없는 첫 단계부터 실행합니다. IN_PROGRESS 기록을 재개하기 전에는 기존 프로세스가 종료되었는지 확인하세요. 같은 앱에 두 실행을 동시에 진행하지 마세요.

기존 기록은 보존되며 새 `.factory/<실행 ID>/resume.json`에 원본 실행과 재개 단계를 기록합니다. 재시도하는 단계의 이전 보고서는 복사하지 않습니다. 기획 단계부터 재개할 때는 원래 `--idea`도 다시 지정하세요.

재개는 현재 앱 파일을 사용하며 과거 소스를 복원하거나 변경 여부를 비교하지 않습니다. 이미 통과한 리뷰 이후 앱 코드를 변경했다면 리뷰가 낡을 수 있으므로 `--resume` 없이 전체 검증을 다시 실행하세요. BUNDLE에서는 타입 검사·린트·테스트·빌드를 다시 수행합니다. 자동 수정 반복은 지원하지 않습니다.

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

## 실행 
python -m orchestrator.orchestrator projects/roulette --idea "점심 메뉴 선택 룰렛"
