"""Static analysis + compile-only sandbox for code blocks.

Two operations are exposed:

  - `analyse(code, lang)` — never runs the code. Returns syntax verdict,
    suspicious-API hits, and quick lints. Always available.

  - `compile(code, lang)` — invokes the local toolchain to *compile* the
    code (no execution). Output binary lives in a per-build temp dir.
    Hard timeout, capped input size, no shell.

Toolchain paths are auto-detected from $PATH but can be overridden with
env vars: DARK_PROMPT_NASM, DARK_PROMPT_MASM, DARK_PROMPT_GCC, etc.
See `.env.example` for the full list.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from django.conf import settings


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_INPUT_BYTES      = 256 * 1024  # 256 KB
COMPILE_TIMEOUT_S    = 30
ANALYSE_TIMEOUT_S    = 5
C_ANALYSE_TIMEOUT_S  = 25  # MinGW cross-compiler is slow on throttled hosts


# ---------------------------------------------------------------------------
# Toolchain detection
# ---------------------------------------------------------------------------

def _resolve_tool(env_name: str, candidates: list[str]) -> Optional[str]:
    """Look up env override first; fall back to scanning $PATH for known names."""
    override = os.environ.get(env_name, "").strip()
    if override and Path(override).exists():
        return override
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def detect_toolchains() -> dict[str, Optional[str]]:
    """Return a map of toolchain name -> absolute path (or None if missing)."""
    return {
        "nasm":   _resolve_tool("DARK_PROMPT_NASM",   ["nasm", "nasm.exe"]),
        # MASM-compatible assemblers, in preference order:
        #   ml64 / ml — Microsoft (Windows only, ships with VS Build Tools)
        #   uasm      — modern MASM-compatible drop-in (Linux + Windows)
        #   jwasm     — UASM's predecessor (still around on some hosts)
        #   tasm      — legacy Borland assembler
        "masm":   _resolve_tool("DARK_PROMPT_MASM",   [
            "ml64.exe", "ml.exe",
            "uasm64.exe", "uasm32.exe", "uasm.exe", "uasm",
            "jwasm.exe", "jwasm",
            "tasm.exe",
        ]),
        "gcc":    _resolve_tool("DARK_PROMPT_GCC",    ["gcc", "gcc.exe"]),
        "clang":  _resolve_tool("DARK_PROMPT_CLANG",  ["clang", "clang.exe"]),
        # MinGW-w64 cross compiler — required to syntax-check / build code that
        # pulls in <windows.h>, <winsock2.h>, <psapi.h>, etc. on a host that
        # isn't Windows itself. If unset we fall back to plain gcc/clang and
        # surface a friendlier "Windows headers unavailable" note.
        "mingw":  _resolve_tool("DARK_PROMPT_MINGW",  [
            "x86_64-w64-mingw32-gcc",
            "i686-w64-mingw32-gcc",
            "x86_64-w64-mingw32-gcc.exe",
        ]),
        "python": _resolve_tool("DARK_PROMPT_PYTHON", ["python", "python3", "python.exe"]),
        "pwsh":   _resolve_tool("DARK_PROMPT_PWSH",   ["pwsh", "pwsh.exe", "powershell.exe"]),
        "bash":   _resolve_tool("DARK_PROMPT_BASH",   ["bash", "bash.exe"]),
        "go":     _resolve_tool("DARK_PROMPT_GO",     ["go", "go.exe"]),
        "rustc":  _resolve_tool("DARK_PROMPT_RUSTC",  ["rustc", "rustc.exe"]),
    }


# Headers / identifiers that mean the source targets Windows. If any of these
# show up we prefer MinGW over the host's plain gcc/clang (which on Linux has
# no `windows.h`).
_WIN_TARGET_RE = re.compile(
    r"(?mi)"
    r"^\s*#\s*include\s*[<\"](windows|winsock2?|ws2tcpip|wininet|winhttp|"
    r"winuser|winnt|winreg|winsvc|tlhelp32|psapi|shlobj|shellapi|wininet|"
    r"setupapi|sddl|aclapi|fileapi|processthreadsapi|synchapi|memoryapi|"
    r"libloaderapi|errhandlingapi|handleapi|winbase|tchar|stdafx|wincrypt|"
    r"bcrypt|ncrypt|wow64apiset|sysinfoapi|profileapi|dbghelp|imagehlp|"
    r"detours|winsock|mmsystem)(\.h)?[>\"]"
)


def _is_windows_targeted(code: str) -> bool:
    return bool(_WIN_TARGET_RE.search(code or ""))


def _pick_c_compiler(code: str) -> tuple[Optional[str], Optional[str]]:
    """Pick the right C compiler for `code`.

    Returns (compiler_path, missing_label). When the source pulls in Windows
    headers we prefer MinGW; when it doesn't, we prefer the host's clang/gcc.
    `missing_label` is set to a user-friendly string when no suitable
    compiler is available so the caller can surface it.
    """
    if _is_windows_targeted(code):
        if TOOLS["mingw"]:
            return TOOLS["mingw"], None
        # Plain gcc/clang on a non-Windows host can't see <windows.h>.
        # On Windows itself a regular gcc is fine — it ships with the SDK.
        if os.name == "nt" and (TOOLS["gcc"] or TOOLS["clang"]):
            return TOOLS["clang"] or TOOLS["gcc"], None
        return None, "x86_64-w64-mingw32-gcc (MinGW)"
    cc = TOOLS["clang"] or TOOLS["gcc"]
    if cc:
        return cc, None
    return None, "clang or gcc"


# Cached at import. Not refreshed at runtime — the dev restarts the server
# after installing a new toolchain anyway.
TOOLS: dict[str, Optional[str]] = detect_toolchains()


# ---------------------------------------------------------------------------
# Suspicious-API library
# ---------------------------------------------------------------------------

# Each entry: (regex, label, mitre_tag_or_note). These are intentionally broad
# pattern-match hits — false positives are fine, the goal is to surface intent
# at a glance. They mirror the MITRE rules already used in chat.js but cover a
# wider lexical surface (Win32 / Linux / macro substring).
SUSPICIOUS_APIS = [
    (r"\bSetWindowsHookEx[AW]?\b",                 "Win32 keyboard / message hook",       "T1056.001"),
    (r"\bGetAsyncKeyState\b",                      "Polled keystroke capture",            "T1056.001"),
    (r"\b(VirtualAllocEx|WriteProcessMemory|CreateRemoteThread|NtMapViewOfSection)\b",
                                                   "Process injection primitives",        "T1055"),
    (r"\b(LoadLibrary[AW]?|GetProcAddress|LdrLoadDll)\b",
                                                   "Dynamic API resolution",              "T1620"),
    (r"\bRegSetValueEx[AW]?\b|HKCU\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run",
                                                   "Registry-based persistence",          "T1547.001"),
    (r"\bSchTasks(\.exe)?\b|\bICreateRemoteSchedule",
                                                   "Scheduled-task persistence",          "T1053.005"),
    (r"\b(OpenProcess|DuplicateHandle|TerminateProcess)\b",
                                                   "Process tampering",                   "T1057"),
    (r"\b(WSAStartup|connect|recv|send|InternetOpen[AW]?|WinHttpOpen|HttpSendRequest[AW]?)\b",
                                                   "Network I/O",                          "T1071"),
    (r"\b(BitBlt|GetDesktopWindow|PrintWindow|GetDC)\b",
                                                   "Screen-capture primitives",           "T1113"),
    (r"\bint\s+0?x?21h?\b|\bDOS Services\b",
                                                   "MS-DOS interrupt 21h",                "(legacy)"),
    (r"\bIsDebuggerPresent\b|\bCheckRemoteDebuggerPresent\b|\bNtQueryInformationProcess\b.*ProcessDebugPort",
                                                   "Debugger detection",                  "T1622"),
    (r"\b(VirtualProtect|mprotect)\s*\(",          "Page-protection change (RWX)",        "T1055"),
    (r"\bCryptEncrypt\b|\bAES_(en|de)crypt\b",     "Symmetric-crypto primitives",         "T1486"),
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    lang:            str
    syntax_ok:       bool                 = False
    syntax_detail:   str                  = ""
    notes:           list[str]            = field(default_factory=list)
    warnings:        list[str]            = field(default_factory=list)
    api_hits:        list[dict]           = field(default_factory=list)
    can_compile:     bool                 = False
    missing_tool:    Optional[str]        = None
    elapsed_ms:      int                  = 0

    def to_dict(self) -> dict:
        return {
            "lang":          self.lang,
            "syntax_ok":     self.syntax_ok,
            "syntax_detail": self.syntax_detail,
            "notes":         self.notes,
            "warnings":      self.warnings,
            "api_hits":      self.api_hits,
            "can_compile":   self.can_compile,
            "missing_tool":  self.missing_tool,
            "elapsed_ms":    self.elapsed_ms,
        }


@dataclass
class CompileResult:
    lang:         str
    ok:           bool                 = False
    stdout:       str                  = ""
    stderr:       str                  = ""
    binary_name:  Optional[str]        = None
    binary_size:  Optional[int]        = None
    download_url: Optional[str]        = None
    elapsed_ms:   int                  = 0

    def to_dict(self) -> dict:
        return {
            "lang":         self.lang,
            "ok":           self.ok,
            "stdout":       self.stdout[-4000:],   # cap output
            "stderr":       self.stderr[-4000:],
            "binary_name":  self.binary_name,
            "binary_size":  self.binary_size,
            "download_url": self.download_url,
            "elapsed_ms":   self.elapsed_ms,
        }


class SandboxError(Exception):
    """Raised for caller-visible refusals (e.g. input too large)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map the JS-side language keys to a canonical internal name.
LANG_ALIASES = {
    "nasm": "nasm", "asm": "nasm", "asm6502": "nasm", "x86": "nasm", "x86_64": "nasm",
    "masm": "masm", "tasm": "masm",
    "c":    "c",
    "cpp":  "cpp", "c++": "cpp", "cxx": "cpp",
    "csharp": "csharp", "cs": "csharp",
    "python": "python", "py": "python",
    "powershell": "powershell", "ps1": "powershell", "ps": "powershell",
    "bash": "bash", "sh": "bash", "shell": "bash",
    "go":   "go", "golang": "go",
    "rust": "rust", "rs": "rust",
    "javascript": "javascript", "js": "javascript",
}


def _canonical_lang(lang: str) -> str:
    return LANG_ALIASES.get((lang or "").strip().lower(), (lang or "").strip().lower())


def _detect_assembly_dialect(code: str) -> str:
    """Pick between MASM/TASM-style and NASM-style based on directives."""
    head = code[:1024]
    if re.search(r"^\s*\.(model|code|data|stack|386|486|586|686)\b", head, re.M | re.I):
        return "masm"
    if re.search(r"^\s*\b(BITS|section\s+\.|global\s+_?\w+|extern\s+\w+)\b", head, re.M | re.I):
        return "nasm"
    return "nasm"  # default


def _enforce_input_size(code: str) -> None:
    if len(code.encode("utf-8", "replace")) > MAX_INPUT_BYTES:
        raise SandboxError(f"input exceeds {MAX_INPUT_BYTES} bytes")


def _scan_apis(code: str) -> list[dict]:
    hits = []
    for pattern, label, tag in SUSPICIOUS_APIS:
        match = re.search(pattern, code, re.IGNORECASE | re.MULTILINE)
        if match:
            hits.append({
                "label":  label,
                "tag":    tag,
                "match":  match.group(0)[:80],
            })
    return hits


def _runtime_dir() -> Path:
    """Per-project scratch dir for build artefacts. Auto-created."""
    base = Path(getattr(settings, "BASE_DIR", ".")) / "runtime" / "builds"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _new_build_dir() -> Path:
    """Per-build subdirectory; cleaned by the caller via shutil.rmtree on error."""
    name = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    p = _runtime_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    """Subprocess wrapper that never uses a shell and always times out."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        # Never inherit the parent shell environment beyond PATH; pass only the
        # bare minimum so the toolchain can find its own libraries.
        env={
            "PATH":   os.environ.get("PATH", ""),
            "TEMP":   os.environ.get("TEMP", str(cwd)),
            "TMP":    os.environ.get("TMP",  str(cwd)),
            "SystemRoot": os.environ.get("SystemRoot", ""),
            "ComSpec":    os.environ.get("ComSpec", ""),
        },
    )


# ---------------------------------------------------------------------------
# analyse(code, lang)
# ---------------------------------------------------------------------------

def _infer_lang_from_code(code: str) -> str:
    """Last-resort language guess from code content when the caller sends no tag."""
    head = code[:2000]
    if re.search(r"^\s*#\s*include\s*[<\"]", head, re.M):
        return "cpp" if re.search(r"\b(std::|namespace\s+std|template\s*<)", code) else "c"
    if re.search(r"^\s*(BITS\s+\d+|section\s+\.|global\s+\w|extern\s+\w)", head, re.M | re.I):
        return "nasm"
    if re.search(r"^\s*def\s+\w+\s*\(|^\s*(import|from)\s+\w+", head, re.M):
        return "python"
    return ""


def analyse(code: str, lang: str) -> AnalysisResult:
    started = time.monotonic()
    _enforce_input_size(code)
    canonical = _canonical_lang(lang)

    # If the frontend sent no language tag, try to guess from code content.
    if not canonical:
        canonical = _infer_lang_from_code(code)

    # Auto-disambiguate assembly: NASM vs MASM/TASM pick from source.
    if canonical == "nasm":
        canonical = _detect_assembly_dialect(code)

    result = AnalysisResult(lang=canonical)
    result.api_hits = _scan_apis(code)

    handler = _ANALYSE_DISPATCH.get(canonical, _analyse_unsupported)
    try:
        handler(code, result)
    except subprocess.TimeoutExpired:
        result.syntax_ok = False
        result.syntax_detail = f"Analyser exceeded {ANALYSE_TIMEOUT_S}s timeout."
    except FileNotFoundError as exc:
        result.syntax_ok = False
        result.syntax_detail = f"Toolchain not found: {exc}"
    except Exception as exc:
        result.syntax_ok = False
        result.syntax_detail = f"Analyser error: {type(exc).__name__}: {exc}"

    result.elapsed_ms = int((time.monotonic() - started) * 1000)
    return result


def _analyse_unsupported(code: str, r: AnalysisResult) -> None:
    r.syntax_ok = False
    r.syntax_detail = f"No analyser registered for {r.lang!r}."
    r.notes.append("Add a handler in chat/sandbox.py to support this language.")


def _analyse_python(code: str, r: AnalysisResult) -> None:
    import ast
    try:
        ast.parse(code)
        r.syntax_ok = True
        r.syntax_detail = "Parses as Python."
        r.can_compile = TOOLS["python"] is not None
        if not r.can_compile:
            r.missing_tool = "python"
    except SyntaxError as exc:
        r.syntax_ok = False
        r.syntax_detail = f"{exc.msg} at line {exc.lineno}, col {exc.offset}"


def _analyse_powershell(code: str, r: AnalysisResult) -> None:
    pwsh = TOOLS["pwsh"]
    if not pwsh:
        r.syntax_ok = True  # we can't check; assume OK with a warning
        r.syntax_detail = "Toolchain not detected; syntax check skipped."
        r.warnings.append("pwsh / powershell.exe not found on PATH.")
        r.missing_tool = "pwsh"
        return
    # `[scriptblock]::Create($code)` parses without executing.
    proc = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command",
         "$code = [Console]::In.ReadToEnd(); "
         "try { [void][scriptblock]::Create($code); 'OK' } "
         "catch { Write-Host ('ERR ' + $_.Exception.Message); exit 1 }"],
        input=code, capture_output=True, text=True, timeout=ANALYSE_TIMEOUT_S, check=False,
    )
    if proc.returncode == 0:
        r.syntax_ok = True
        r.syntax_detail = "PowerShell parser accepted the script."
        r.can_compile = True   # pwsh "compile" === parse-OK
    else:
        r.syntax_ok = False
        r.syntax_detail = (proc.stdout + proc.stderr).strip()[:400]


def _analyse_bash(code: str, r: AnalysisResult) -> None:
    bash = TOOLS["bash"]
    if not bash:
        r.warnings.append("bash not found on PATH.")
        r.missing_tool = "bash"
        return
    proc = subprocess.run(
        [bash, "-n"], input=code,
        capture_output=True, text=True, timeout=ANALYSE_TIMEOUT_S, check=False,
    )
    r.syntax_ok = proc.returncode == 0
    r.syntax_detail = "bash -n accepted." if r.syntax_ok else proc.stderr.strip()[:400]
    r.can_compile = r.syntax_ok


def _analyse_c(code: str, r: AnalysisResult) -> None:
    cc, missing = _pick_c_compiler(code)
    if not cc:
        # The source needs Windows headers but this host has no MinGW.
        # Don't report it as a syntax error — surface a softer note so the
        # user understands it's an environment limitation, not bad code.
        r.warnings.append(
            "Windows-targeted source — install MinGW-w64 (or set "
            "DARK_PROMPT_MINGW) to enable static analysis here."
        )
        r.missing_tool = missing
        # The code itself is structurally valid as far as we can tell; let
        # the user still see the API hits + MITRE pills.
        r.syntax_ok = True
        r.syntax_detail = (
            "Skipped — host has no Windows SDK / MinGW headers."
        )
        r.can_compile = False
        return
    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False, encoding="utf-8") as f:
        f.write(code); src = f.name
    try:
        proc = subprocess.run(
            # -Wall omitted: we only need syntax validity, not quality warnings.
            # -fmax-errors=5: stop early so the compiler doesn't scan the whole
            # file looking for more errors on a throttled host.
            [cc, "-fsyntax-only", "-fmax-errors=5", src],
            capture_output=True, text=True, timeout=C_ANALYSE_TIMEOUT_S, check=False,
        )
    finally:
        try: os.unlink(src)
        except OSError: pass
    r.syntax_ok = proc.returncode == 0
    r.syntax_detail = "Syntax check passed." if r.syntax_ok else proc.stderr.strip()[:600]
    if not r.syntax_ok and proc.stderr:
        for line in proc.stderr.splitlines():
            if "warning:" in line:
                r.warnings.append(line.strip()[:200])
    r.can_compile = r.syntax_ok


def _analyse_assembly(code: str, r: AnalysisResult, *, masm_style: bool) -> None:
    tool_key = "masm" if masm_style else "nasm"
    tool = TOOLS[tool_key]
    if not tool:
        # If the user wrote MASM-style but only NASM is installed, warn but
        # don't try to run it — syntax differs enough to matter.
        r.warnings.append(
            f"{'MASM/TASM' if masm_style else 'NASM'} assembler not detected."
        )
        r.missing_tool = tool_key
        # Lightweight regex-only sanity check
        if re.search(r"^\s*(section|\.code|\.data|start:|main:)\s*$", code, re.M | re.I):
            r.syntax_ok = True
            r.syntax_detail = "Looks structurally valid (no assembler available)."
        return
    if masm_style:
        # ml.exe / jwasm: assemble without linking with /c
        with tempfile.NamedTemporaryFile("w", suffix=".asm", delete=False, encoding="utf-8") as f:
            f.write(code); src = f.name
        try:
            proc = subprocess.run(
                [tool, "/c", "/nologo", src],
                capture_output=True, text=True, timeout=ANALYSE_TIMEOUT_S, check=False,
                cwd=str(Path(src).parent),
            )
        finally:
            try: os.unlink(src)
            except OSError: pass
        r.syntax_ok = proc.returncode == 0
        r.syntax_detail = (proc.stdout + proc.stderr).strip()[:600] or "Assembled OK."
    else:
        # nasm: try a parse-only assembly. -f bin keeps it simple.
        with tempfile.NamedTemporaryFile("w", suffix=".asm", delete=False, encoding="utf-8") as f:
            f.write(code); src = f.name
        try:
            proc = subprocess.run(
                [tool, "-f", "bin", "-o", os.devnull, src],
                capture_output=True, text=True, timeout=ANALYSE_TIMEOUT_S, check=False,
            )
        finally:
            try: os.unlink(src)
            except OSError: pass
        r.syntax_ok = proc.returncode == 0
        r.syntax_detail = proc.stderr.strip()[:600] or "Assembled OK."
    r.can_compile = r.syntax_ok


_ANALYSE_DISPATCH = {
    "python":     _analyse_python,
    "powershell": _analyse_powershell,
    "bash":       _analyse_bash,
    "c":          _analyse_c,
    "cpp":        _analyse_c,
    "nasm":       lambda code, r: _analyse_assembly(code, r, masm_style=False),
    "masm":       lambda code, r: _analyse_assembly(code, r, masm_style=True),
}


# ---------------------------------------------------------------------------
# compile(code, lang) — toolchain-specific full compile
# ---------------------------------------------------------------------------

def compile_code(code: str, lang: str) -> CompileResult:
    started = time.monotonic()
    _enforce_input_size(code)
    canonical = _canonical_lang(lang)
    if canonical == "nasm":
        canonical = _detect_assembly_dialect(code)

    result = CompileResult(lang=canonical)
    handler = _COMPILE_DISPATCH.get(canonical)
    if handler is None:
        result.ok = False
        result.stderr = f"No compiler registered for {canonical!r}."
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        return result

    build = _new_build_dir()
    try:
        handler(code, result, build)
    except subprocess.TimeoutExpired:
        result.ok = False
        result.stderr = f"Compiler exceeded {COMPILE_TIMEOUT_S}s timeout."
    except FileNotFoundError as exc:
        result.ok = False
        result.stderr = f"Toolchain not found: {exc}"
    except Exception as exc:
        result.ok = False
        result.stderr = f"Sandbox error: {type(exc).__name__}: {exc}"
    finally:
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
    return result


def _compile_finalize(result: CompileResult, build: Path, binary: Path) -> None:
    if binary.exists():
        result.ok = True
        result.binary_name = binary.name
        result.binary_size = binary.stat().st_size
        # The download URL is built by the view (it has the request scheme).
        result.download_url = f"__BUILD__/{build.name}/{binary.name}"
    else:
        result.ok = False
        if not result.stderr:
            result.stderr = "Compiler returned 0 but produced no binary."


def _compile_python(code: str, r: CompileResult, build: Path) -> None:
    """Python 'compile' === bytecode-compile (.pyc), no execution."""
    src = build / "module.py"
    src.write_text(code, encoding="utf-8")
    py = TOOLS["python"]
    if not py:
        r.stderr = "python not found."; return
    proc = _run([py, "-m", "py_compile", str(src)], cwd=build, timeout=COMPILE_TIMEOUT_S)
    r.stdout, r.stderr = proc.stdout, proc.stderr
    pyc = next(iter((build / "__pycache__").glob("*.pyc")), None) if (build / "__pycache__").exists() else None
    if proc.returncode == 0 and pyc:
        # Move the .pyc up so the download URL is stable.
        target = build / "module.pyc"
        pyc.replace(target)
        _compile_finalize(r, build, target)
    else:
        r.ok = False


def _compile_powershell(code: str, r: CompileResult, build: Path) -> None:
    """PowerShell doesn't compile to a binary; we write the script + verify parse."""
    src = build / "script.ps1"
    src.write_text(code, encoding="utf-8")
    pwsh = TOOLS["pwsh"]
    if not pwsh:
        r.stderr = "pwsh not found."; return
    proc = _run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command",
         f"$c = Get-Content -Raw '{src}'; "
         "[void][scriptblock]::Create($c); 'OK'"],
        cwd=build, timeout=COMPILE_TIMEOUT_S,
    )
    r.stdout, r.stderr = proc.stdout, proc.stderr
    if proc.returncode == 0:
        _compile_finalize(r, build, src)
    else:
        r.ok = False


def _compile_bash(code: str, r: CompileResult, build: Path) -> None:
    src = build / "script.sh"
    src.write_text(code, encoding="utf-8")
    bash = TOOLS["bash"]
    if not bash:
        r.stderr = "bash not found."; return
    proc = _run([bash, "-n", str(src)], cwd=build, timeout=COMPILE_TIMEOUT_S)
    r.stdout, r.stderr = proc.stdout, proc.stderr
    if proc.returncode == 0:
        _compile_finalize(r, build, src)
    else:
        r.ok = False


def _compile_c(code: str, r: CompileResult, build: Path, *, cpp: bool = False) -> None:
    cc, missing = _pick_c_compiler(code)
    if not cc:
        r.stderr = (
            f"{missing} not found — required to build Windows-targeted "
            "C source on this host."
        )
        return
    ext = ".cpp" if cpp else ".c"
    src = build / f"main{ext}"
    src.write_text(code, encoding="utf-8")
    # MinGW always emits a PE; native gcc/clang follow the host convention.
    is_mingw = "mingw" in (cc or "").lower()
    binary = build / ("main.exe" if (os.name == "nt" or is_mingw) else "main")
    proc = _run([cc, str(src), "-o", str(binary), "-Wall"],
                cwd=build, timeout=COMPILE_TIMEOUT_S)
    r.stdout, r.stderr = proc.stdout, proc.stderr
    _compile_finalize(r, build, binary)


def _compile_nasm(code: str, r: CompileResult, build: Path) -> None:
    tool = TOOLS["nasm"]
    if not tool:
        r.stderr = "nasm not found."; return
    src = build / "input.asm"
    src.write_text(code, encoding="utf-8")
    binary = build / "input.bin"
    proc = _run([tool, "-f", "bin", "-o", str(binary), str(src)],
                cwd=build, timeout=COMPILE_TIMEOUT_S)
    r.stdout, r.stderr = proc.stdout, proc.stderr
    _compile_finalize(r, build, binary)


def _compile_masm(code: str, r: CompileResult, build: Path) -> None:
    tool = TOOLS["masm"]
    if not tool:
        r.stderr = "MASM/TASM/JWASM not found."; return
    src = build / "input.asm"
    src.write_text(code, encoding="utf-8")
    proc = _run([tool, "/c", "/nologo", str(src)], cwd=build, timeout=COMPILE_TIMEOUT_S)
    r.stdout, r.stderr = proc.stdout, proc.stderr
    obj = next(iter(build.glob("*.obj")), None)
    if proc.returncode == 0 and obj is not None:
        _compile_finalize(r, build, obj)
    else:
        r.ok = False


_COMPILE_DISPATCH = {
    "python":     _compile_python,
    "powershell": _compile_powershell,
    "bash":       _compile_bash,
    "c":          _compile_c,
    "cpp":        lambda code, r, build: _compile_c(code, r, build, cpp=True),
    "nasm":       _compile_nasm,
    "masm":       _compile_masm,
}


def serve_build_artefact(build_name: str, file_name: str) -> Optional[Path]:
    """Resolve a download URL back to a real path, with traversal guards."""
    base = _runtime_dir().resolve()
    target = (base / build_name / file_name).resolve()
    # Must stay inside the runtime/builds tree.
    if not str(target).startswith(str(base)):
        return None
    if not target.exists() or not target.is_file():
        return None
    return target
