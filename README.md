# Toss MiniApp AI Factory (토스 미니앱 자동화 개발 공장)

> **Codex + Claude Code + Antigravity** 3개의 AI 에이전트를 오케스트레이션하여, 토스 미니앱(Apps in Toss)을 아이디어 기획부터 코드 구현, UI/규격 검증, 번들 생성 및 심사 제출 준비까지 자동화하는 시스템입니다.

---

## 🏗️ 1. 시스템 아키텍처

```
[ 사용자 ]  ── "오늘의 선택 룰렛 미니앱 만들어줘" ──┐
                                                    ▼
┌────────────────────────────────────────────────────────┐
│             AI Factory Orchestrator (Python)           │
│  - 작업 큐 & 상태 머신 (State Machine)                 │
│  - CLI 비대화형 파이프라인 제어                        │
│  - 결과 검증 (Git Diff / Vitest / Playwright)          │
└────────┬───────────────────┬───────────────────┬───────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│   Claude Code    ││      Codex       ││   Antigravity    │
│  (`claude -p`)   ││  (`codex exec`)  ││    (`agy -p`)    │
│  - PRD / 기획서  ││  - 컴포넌트 구현 ││  - UI/UX 사용성  │
│  - 태스크 쪼개기 ││  - 비즈니스 로직 ││  - 모바일 웹뷰뷰 │
│  - 아키텍처 리뷰 ││  - 단위 테스트   ││  - 규격/심사서류 │
└──────────────────┘└──────────────────┘└──────────────────┘
         ▲                   ▲                   ▲
         └───────────────────┴───────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│           토스 공식 Apps in Toss Harness & MCP         │
│  - `@apps-in-toss/create-app` (프로젝트 템플릿)        │
│  - `ait` 플러그인 & MCP Console 연동                   │
│  - `.ait` 번들 생성 및 심사(Inspection) 준비           │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 2. 사전 준비 (토스 공식 Harness & 환경)

### 2.1 필수 런타임
* **Node.js**: v24 이상 권장
* **Python**: 3.10 이상
* **Git**: 설치 및 사용자 설정 완료
* [토스 개발자센터(Apps in Toss)](https://developers-apps-in-toss.toss.im/) 파트너 계정

### 2.2 Claude Code에 토스 공식 플러그인 설치
Claude Code를 실행한 후 대화창에 아래 명령을 순서대로 실행합니다:
```text
/plugin marketplace add toss/apps-in-toss-harness
/plugin install ait@apps-in-toss
/mcp
/plugin
/ait:welcome
```
* `/mcp`: `ait-console` 토스 계정 인증 연동
* `/ait:plan`: 토스 미니앱 기획 생성
* `/ait:new`: 미니앱 보일러플레이트 자동 생성

---

## 📂 3. 디렉토리 구조

```text
C:\Users\Lenovo\Desktop\anti/
├── README.md                  # 시스템 개요 및 가이드
├── configs/
│   └── agents.yaml            # 3대 AI CLI 호출 설정 및 프롬프트
├── orchestrator/
│   ├── task_schema.py         # AI 간 구조화된 JSON 메시지 규격
│   └── orchestrator.py        # 파이프라인 실행 엔진 (Python)
├── integrations/
│   └── toss_harness.py        # 토스 공식 Harness 및 빌드 래퍼
└── projects/
    └── roulette/              # 첫 번째 파일럿 미니앱 (룰렛)
        └── PRD.md             # 룰렛 앱 기획 및 심사 체크리스트
```

---

## 🔄 4. 6단계 자동화 프로세스

1. **아이디어 분석 (Claude Code)**: 사용자 요청을 받아 `PRD.md` 및 `tasks.json` 생성.
2. **코드 생성 (Codex)**: 토스 SDK 기반 React + TypeScript 컴포넌트 구현 및 빌드 검증.
3. **UI/사용성 검증 (Antigravity)**: 모바일 웹뷰(Safe Area, 100dvh, TDS 스타일) 및 브릿지 Mock 동작 점검.
4. **교차 검증 (Claude Code + Codex)**: 토스 심사 가이드라인 위반 여부(외부 링크, 결제, 개인정보) 점검.
5. **번들 패키징 & 검수 준비**: `.ait` 번들 패키징 및 콘솔 업로드 준비.
6. **최종 승인 및 출시**: 사용자 승인(Human-in-the-loop) 후 토스 콘솔에서 출시.
