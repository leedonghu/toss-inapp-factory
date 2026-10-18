"""Argument-safe subprocess execution, including npm on Windows."""
# 외부 CLI(claude, codex, npm 등)를 셸을 거치지 않고 안전하게 실행하는 유틸리티.
# Windows에서는 npm이 설치한 CLI가 .cmd 래퍼로 제공되는데, .cmd를 실행하려면 cmd.exe를
# 거쳐야 하고 그 과정에서 인자가 셸 해석(&, |, % 등)을 받아 인젝션 위험이 생긴다.
# 그래서 .cmd 래퍼 대신 그 안에 적힌 실제 JS 진입점을 찾아 node로 직접 실행한다.
import re
import shutil
import subprocess
from pathlib import Path


class CommandError(RuntimeError):
    """외부 명령을 찾지 못했거나, 실행 실패·타임아웃·비정상 종료했을 때 발생하는 예외."""
    pass


# npm이 생성한 .cmd 래퍼 안의 `"%dp0%\node_modules\...\xxx.js"` 부분에서 JS 경로를 추출하는 정규식.
# %dp0%는 래퍼 파일이 있는 디렉터리를 뜻한다. .js / .cjs / .mjs 모두 허용.
NPM_SHIM_SCRIPT = re.compile(r'"%dp0%\\(node_modules\\[^"%]+\.(?:c|m)?js)"', re.IGNORECASE)


def npm_shim_script(wrapper):
    """Return the JS entry point of an npm-generated .cmd shim, or None."""
    try:
        match = NPM_SHIM_SCRIPT.search(Path(wrapper).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    # %dp0%를 래퍼의 부모 디렉터리로 치환한 실제 경로. 파일이 실제로 있을 때만 인정한다.
    script = Path(wrapper).parent / match.group(1) if match else None
    return script if script and script.is_file() else None


def resolve_command(command):
    """명령 리스트의 첫 요소를 PATH에서 찾아, shell=False로 실행 가능한 형태로 변환한다.

    - 네이티브 실행 파일이면 절대 경로로 바꿔 그대로 반환한다.
    - .cmd/.bat 래퍼면 `node <js 진입점> ...` 형태로 바꾼다.
    - JS 진입점을 알 수 없는 배치 파일은 셸 인젝션 위험 때문에 거부한다(fail-closed).
    """
    executable = shutil.which(command[0])
    if not executable:
        raise CommandError(f"Executable not found: {command[0]}")
    if Path(executable).suffix.lower() in (".cmd", ".bat"):
        node = shutil.which("node")
        if Path(executable).stem.lower() in ("npm", "npx"):
            # npm/npx 자체는 node 설치 폴더의 node_modules/npm/bin/*-cli.js가 진입점이다.
            script = Path(executable).parent / "node_modules" / "npm" / "bin" / f"{Path(executable).stem.lower()}-cli.js"
        else:
            # 그 외 npm 전역 설치 CLI는 .cmd 래퍼 내용을 파싱해 진입점을 찾는다.
            script = npm_shim_script(executable)
        if node and script and script.is_file():
            return [node, str(script), *command[1:]]
        raise CommandError(f"Use a native executable or explicit node adapter instead of a batch wrapper: {executable}")
    return [executable, *command[1:]]


def run_command(command, cwd, timeout=900, input_text=None, log_prefix=None):
    """명령을 실행하고 stdout을 반환한다. 실패하면 CommandError를 던진다.

    Args:
        command: 실행할 명령과 인자 리스트 (예: ["npm", "run", "build"]).
        cwd: 작업 디렉터리.
        timeout: 최대 실행 시간(초). 초과하면 프로세스를 종료하고 실패 처리.
        input_text: stdin으로 전달할 문자열 (에이전트 프롬프트 전달에 사용).
        log_prefix: 지정하면 `<prefix>.stdout.log` / `<prefix>.stderr.log`로 출력을 저장.
    """
    resolved = resolve_command(command)
    try:
        # shell=False + 인자 리스트로 실행해 인자가 셸 해석을 받지 않도록 한다.
        # 한글 프롬프트가 깨지지 않도록 UTF-8로 고정하고, 디코딩 불가 바이트는 대체한다.
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
        # 오류 메시지가 너무 길어지지 않도록 출력의 마지막 4000자만 포함한다.
        raise CommandError(f"{command[0]} exited {result.returncode}: {(result.stderr or result.stdout)[-4000:]}")
    return result.stdout
