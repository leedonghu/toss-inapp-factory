"""Argument-safe subprocess execution, including npm on Windows."""
import re
import shutil
import subprocess
from pathlib import Path


class CommandError(RuntimeError):
    pass


NPM_SHIM_SCRIPT = re.compile(r'"%dp0%\\(node_modules\\[^"%]+\.(?:c|m)?js)"', re.IGNORECASE)


def npm_shim_script(wrapper):
    """Return the JS entry point of an npm-generated .cmd shim, or None."""
    try:
        match = NPM_SHIM_SCRIPT.search(Path(wrapper).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    script = Path(wrapper).parent / match.group(1) if match else None
    return script if script and script.is_file() else None


def resolve_command(command):
    executable = shutil.which(command[0])
    if not executable:
        raise CommandError(f"Executable not found: {command[0]}")
    if Path(executable).suffix.lower() in (".cmd", ".bat"):
        node = shutil.which("node")
        if Path(executable).stem.lower() in ("npm", "npx"):
            script = Path(executable).parent / "node_modules" / "npm" / "bin" / f"{Path(executable).stem.lower()}-cli.js"
        else:
            script = npm_shim_script(executable)
        if node and script and script.is_file():
            return [node, str(script), *command[1:]]
        raise CommandError(f"Use a native executable or explicit node adapter instead of a batch wrapper: {executable}")
    return [executable, *command[1:]]


def run_command(command, cwd, timeout=900, input_text=None, log_prefix=None):
    resolved = resolve_command(command)
    try:
        result = subprocess.run(resolved, cwd=str(cwd), input=input_text,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", shell=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"{command[0]} timed out after {timeout}s") from exc
    except OSError as exc:
        raise CommandError(f"Could not execute {command[0]}: {exc}") from exc
    if log_prefix:
        Path(f"{log_prefix}.stdout.log").write_text(result.stdout, encoding="utf-8")
        Path(f"{log_prefix}.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise CommandError(f"{command[0]} exited {result.returncode}: {(result.stderr or result.stdout)[-4000:]}")
    return result.stdout
