# 오늘의 선택 룰렛

점심 메뉴를 넣고 돌리면, 같은 확률로 오늘의 한 끼를 골라주는 미니앱입니다.

**키워드:** 점심, 메뉴 추천, 룰렛, 랜덤 선택, 오늘 뭐 먹지

## 로컬 실행

Node.js 24 이상을 권장합니다. 현재 Apps in Toss 번들 포맷 도구가 Node 24를 요구합니다. 이 프로젝트는 개발 의존성으로 Node 24도 설치하며 npm 스크립트에서 해당 실행 파일을 사용합니다. 캐시는 프로젝트의 `.npm-cache/`에만 저장합니다.

```sh
npm install
npm run dev
npm run typecheck
npm run lint
npm run test
npm run build
npm run bundle
```

- `dev`: 브라우저 개발 서버, 포트 5173. 실기기 접근용으로 host를 열어 둡니다.
- `test`: Vitest 단위·컴포넌트 테스트, watch 없이 종료합니다.
- `build`: TypeScript 검사 및 Vite 프로덕션 빌드 → `dist/`.
- `bundle`: 새 웹 빌드 → 공식 `ait build` → `today-lunch-roulette.ait`의 크기가 0보다 큰지 검사합니다.
- 배포·업로드 스크립트가 없습니다. 이 작업에서 배포, 업로드, 콘솔 등록을 하지 않았습니다.

Windows의 제한된 실행 환경에서 Vite의 기본 설정 로더가 자식 프로세스를 생성하지 못해, Node의 네이티브 설정 로더(`--configLoader native`)와 `preserveSymlinks`를 사용합니다. 최신 Vite 8은 Rolldown으로 빌드합니다. Node 20으로 설치한 경우 일부 선택적 네이티브 패키지가 생략될 수 있으므로 Node 24에서 설치하세요. `.npmrc`의 `foreground-scripts=true`는 설치 스크립트를 일반 상속 입출력으로 실행하게 합니다.

## 구현

- 점심 메뉴 기본값 8개, 추가·삭제·초기화, 12개 제한, 20자 제한, 대소문자·공백 무시 중복 검사.
- `localStorage` 저장·복원. 읽기 실패/손상 데이터는 기본값, 쓰기 실패는 현재 편집을 유지하면서 저장 실패 안내. 서버 저장 없음.
- 시작 시 균등 확률로 결과 선택. 최소 4바퀴, 3.6초 가속·감속, 섹터 내부 오프셋 계산. 회전 중 편집과 중복 실행 잠금.
- 모션 줄이기 설정에서는 120ms. 결과 다이얼로그는 기본 브라우저 모달의 포커스 제한과 Escape 닫기를 사용합니다.
- 햅틱·복사·공유는 `src/platform/`에서만 SDK를 호출하고 지원되지 않으면 브라우저 기능으로 폴백합니다. 모든 기능 실패는 예외 대신 결과값을 반환합니다.
- `/privacy`, `/terms` 내부 경로, 알 수 없는 경로는 메인으로 표시. 별도 상단 내비게이션을 만들지 않습니다.
- `100dvh`, safe-area, 스크롤 바운스 방지, 최소 44px 터치 영역, SVG 텍스트 및 긴 이름 말줄임.
- 앱의 계산과 편집은 외부 API 없이 동작합니다. `.ait`에 웹 자산을 포함합니다. 일반 브라우저는 최초 자산 로드가 필요하며 오프라인 새로고침을 위한 서비스워커는 없습니다.

TDS를 검토하고 `@toss/tds-mobile`의 실제 버튼과 기본 Provider를 사용했습니다. AIT 전용 Provider는 네이티브 브리지가 없는 브라우저에서 safe-area 오류를 로깅하므로 사용하지 않습니다. safe-area는 CSS로 처리합니다. TDS를 포함한 프로덕션 JS는 약 387KB gzip이며 Vite의 500KB 비압축 청크 경고가 있습니다. 빌드 실패는 아닙니다.

## 현행 공식 SDK와 PRD의 차이

2026-10-18에 공식 문서와 설치된 `@apps-in-toss/web-framework@3.8.0` 타입을 대조했습니다.

| PRD의 2.x 표기 | 실제 3.8.0 구현 |
| --- | --- |
| `generateHapticFeedback({ type })` | `Device.triggerHaptic({ type })` |
| `setClipboardText(text)` | `Clipboard.setText(text)` |
| `share({ message })` | `Share.sendMessage({ message })` |
| 환경 확인 | `Environment.environment`, 읽기 실패 시 브라우저 모드 |
| `granite.config.ts` | 활성 설정은 `apps-in-toss.config.ts` |

PRD에서 요구한 `granite.config.ts`는 앱 이름, 표시 이름, 색상, 로컬 아이콘, web 설정과 권한 목록을 보존하는 호환 메타데이터입니다. v3에서는 표시 이름과 아이콘, web 명령 설정이 활성 config에서 제거되었습니다. 실제 빌드는 v3 설정과 package.json 명령을 사용합니다. `Clipboard.setText`는 권한이 필요하므로 클립보드 쓰기 권한(`{ name: 'clipboard', access: 'write' }`)만 선언합니다. 네이티브 복사가 실패하면 브라우저 폴백 및 안내가 동작합니다. 그 외 권한은 요청하지 않습니다.

공식 문서:

- [웹 프로젝트 SDK 연동](https://developers-apps-in-toss.toss.im/ai-vibe-coding/tutorials/webview.md)
- [v3 변경 사항과 설정 마이그레이션](https://developers-apps-in-toss.toss.im/documentation/sdk/v3)
- [햅틱 API](https://developers-apps-in-toss.toss.im/documentation/sdk/domains-api/device/device.triggerhaptic)
- [클립보드 API](https://developers-apps-in-toss.toss.im/documentation/sdk/domains-api/clipboard/clipboard.settext)
- [공유 API](https://developers-apps-in-toss.toss.im/documentation/sdk/domains-api/share/share.sendmessage)
- [운영 환경](https://developers-apps-in-toss.toss.im/documentation/sdk/domains-api/environment/environment.environment)

기존 웹뷰 시작 가이드와 v3 마이그레이션 문서에 차이가 있어 최신 v3 문서 및 설치 타입을 우선했습니다. v3는 기존 샌드박스 앱을 지원하지 않습니다. 실제 토스 검증은 향후 별도로 승인된 콘솔/QR 테스트 과정이 필요하며 이번 작업에는 포함하지 않았습니다.

## 검증과 남은 수동 확인

자동 테스트 35개가 항목 규칙, 저장 실패/손상, 모든 2–12개 섹터의 결과 일치, 시드 난수의 대량 분포, SDK/브라우저 부재와 예외, 편집/회전 잠금, 결과 복사/공유 안내, Clipboard API 없는 환경의 복사 폴백, 공유 창 취소, 모션 줄이기, 타이머 정리, 내부 경로, 정적 금지사항, 실제 SDK를 로드한 브리지 없는 DOM 스모크를 검증합니다.

- [x] `npm run typecheck`
- [x] `npm run lint` (경고 0)
- [x] `npm run test` (35개)
- [x] `npm run build`
- [x] `npm run bundle` 및 0보다 큰 `.ait` 생성
- [x] 설치 의존성 감사: 알려진 취약점 0개
- [x] 실제 브라우저 검증 (2026-10-18, 개발 서버): 360×640·390×844·430×932 가로 넘침 없음, 콘솔 오류 0개, 외부 요청 0개, 돌리기·결과 복사·메뉴 추가/중복 검사·저장 복원·`/privacy`·`/terms`·뒤로가기 정상
- [x] 휴대폰 브라우저에서 화면·복사 확인 (2026-10-18). 일반 HTTP 주소에서는 Web Share API가 없어 공유하기가 복사로 대체되는 것이 정상입니다. 토스 앱에서는 SDK 공유를 사용합니다.
- [ ] VoiceOver/TalkBack 결과 낭독 및 모달 포커스 확인
- [ ] 토스 앱의 실제 햅틱·공유·클립보드와 플랫폼 뒤로가기 확인
- [ ] 출시 전 콘솔 appName 일치, 표시 이름과 정식 아이콘 등록, 약관 내용 검토

실브라우저 검증용 `scripts/browser-smoke.ts`는 포트 9227의 **로컬 테스트 전용 Chrome**에 연결합니다. 개발 서버를 켜고 해당 포트로 디버깅을 활성화한 테스트 브라우저를 실행한 환경에서 아래 명령으로 화면 크기, 저장 복원, 오프라인 상호작용, 결과와 포인터 일치, 콘솔 오류, 외부 요청을 확인할 수 있습니다. 스크린샷은 `test-results/`에 저장합니다. 이번 환경에서는 브라우저 시작 단계가 차단되어 이 스크립트는 통과하지 못했습니다.

```sh
node scripts/browser-smoke.ts
```

원본 `PRD.md`는 검증된 체크리스트 항목만 갱신했고, `.factory/1d4444f4f9a749f4be6073afaac6b306/tasks.json`은 변경하지 않았습니다.
