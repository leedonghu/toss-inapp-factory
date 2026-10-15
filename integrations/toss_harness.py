"""Validate package scripts and actual Apps in Toss bundle artifacts."""
import json
import re
from pathlib import Path
from orchestrator.process import CommandError, run_command


class TossHarnessIntegration:
    def __init__(self, project_path, timeout=900):
        self.project_path = Path(project_path).resolve()
        self.timeout = timeout

    def init_miniapp_template(self, app_name):
        if not re.fullmatch(r"[a-z][a-z0-9-]*", app_name):
            raise ValueError("app_name must contain lowercase letters, digits and hyphens")
        if app_name != self.project_path.name:
            raise ValueError("app_name must match project directory")
        if self.project_path.exists() and any(self.project_path.iterdir()):
            raise ValueError("Scaffold into an empty directory; preserve existing files")
        run_command(["npx", "--yes", "create-ait-app", app_name], self.project_path.parent, self.timeout)
        if not (self.project_path / "package.json").is_file():
            raise CommandError("Scaffolder did not create package.json")
        return True

    def run_script(self, name):
        package = json.loads((self.project_path / "package.json").read_text(encoding="utf-8-sig"))
        if not isinstance(package, dict) or not isinstance(package.get("scripts"), dict):
            raise ValueError("package.json must contain a scripts object")
        script = package.get("scripts", {}).get(name)
        if not isinstance(script, str) or not script.strip():
            raise ValueError(f"Required package.json script missing: {name}")
        return run_command(["npm", "run", name], self.project_path, self.timeout)

    def bundles(self):
        return {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in self.project_path.rglob("*.ait")
                if not any(part in ("node_modules", ".git", ".factory") for part in p.relative_to(self.project_path).parts)
                and p.is_file() and p.resolve().is_relative_to(self.project_path)}

    def build_ait_bundle(self):
        before = self.bundles()
        self.run_script("bundle")
        fresh = [p for p, signature in self.bundles().items()
                 if signature[1] > 0 and before.get(p) != signature]
        if not fresh:
            raise CommandError("Bundle command produced no new or updated nonempty .ait artifact")
        return str(max(fresh, key=lambda p: p.stat().st_mtime_ns))

    def run_typecheck_and_lint(self):
        self.run_script("typecheck")
        self.run_script("lint")
        return True
