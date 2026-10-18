"""Validate package scripts and actual Apps in Toss bundle artifacts."""
# 생성된 앱인토스(Apps in Toss) 프로젝트에 대해 npm 스크립트를 실행하고,
# 실제로 .ait 번들이 만들어졌는지 검증하는 하네스.
import json
import re
from pathlib import Path
from orchestrator.process import CommandError, run_command


class TossHarnessIntegration:
    def __init__(self, project_path, timeout=900):
        self.project_path = Path(project_path).resolve()
        self.timeout = timeout  # 각 npm 명령의 최대 실행 시간(초)
        # 지정하면 npm 출력을 `<log_prefix>-<스크립트>.stdout.log` / `.stderr.log`로 남긴다.
        self.log_prefix = None

    def init_miniapp_template(self, app_name):
        """create-ait-app으로 빈 디렉터리에 미니앱 템플릿을 생성한다."""
        # 앱 이름은 명령 인자로 넘어가므로 소문자·숫자·하이픈만 허용해 이상한 입력을 차단한다.
        if not re.fullmatch(r"[a-z][a-z0-9-]*", app_name):
            raise ValueError("app_name must contain lowercase letters, digits and hyphens")
        if app_name != self.project_path.name:
            raise ValueError("app_name must match project directory")
        # 기존 파일을 덮어쓰지 않도록 비어 있는 디렉터리에만 생성한다.
        if self.project_path.exists() and any(self.project_path.iterdir()):
            raise ValueError("Scaffold into an empty directory; preserve existing files")
        run_command(["npx", "--yes", "create-ait-app", app_name], self.project_path.parent, self.timeout)
        if not (self.project_path / "package.json").is_file():
            raise CommandError("Scaffolder did not create package.json")
        return True

    def run_script(self, name):
        """package.json에 정의된 스크립트를 `npm run <name>`으로 실행한다.

        스크립트가 없으면 npm이 조용히 넘어가는 경우를 막기 위해 먼저 존재 여부를 확인한다.
        """
        package = json.loads((self.project_path / "package.json").read_text(encoding="utf-8-sig"))
        if not isinstance(package, dict) or not isinstance(package.get("scripts"), dict):
            raise ValueError("package.json must contain a scripts object")
        script = package.get("scripts", {}).get(name)
        if not isinstance(script, str) or not script.strip():
            raise ValueError(f"Required package.json script missing: {name}")
        log_prefix = f"{self.log_prefix}-{name}" if self.log_prefix else None
        return run_command(["npm", "run", name], self.project_path, self.timeout, log_prefix=log_prefix)

    def bundles(self):
        """프로젝트 안의 .ait 파일을 찾아 {경로: (수정시각 ns, 크기)} 형태로 반환한다.

        node_modules, .git, .factory(실행 기록) 아래와 심볼릭 링크로 프로젝트 밖을
        가리키는 파일은 제외한다.
        """
        return {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in self.project_path.rglob("*.ait")
                if not any(part in ("node_modules", ".git", ".factory") for part in p.relative_to(self.project_path).parts)
                and p.is_file() and p.resolve().is_relative_to(self.project_path)}

    def build_ait_bundle(self):
        """`npm run bundle`을 실행하고, 이번 실행으로 새로 생기거나 갱신된 .ait 경로를 반환한다."""
        # 실행 전후의 (수정시각, 크기)를 비교해, 예전에 만들어진 번들을 결과로 착각하지 않게 한다.
        before = self.bundles()
        self.run_script("bundle")
        fresh = [p for p, signature in self.bundles().items()
                 if signature[1] > 0 and before.get(p) != signature]
        if not fresh:
            raise CommandError("Bundle command produced no new or updated nonempty .ait artifact")
        # 여러 개면 가장 최근에 수정된 번들을 결과로 사용한다.
        return str(max(fresh, key=lambda p: p.stat().st_mtime_ns))

    def run_typecheck_and_lint(self):
        """타입 체크와 린트를 순서대로 실행한다. 하나라도 실패하면 CommandError."""
        self.run_script("typecheck")
        self.run_script("lint")
        return True
