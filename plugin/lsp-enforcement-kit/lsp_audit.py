"""
LSP/ACP Post-Write Code Auditor & Quality Gate for Antigravity CLI.
Ponytail (ULTRA) Architecture:
- Python stdlib only (zero pip dependencies).
- Circuit breaker on Stop hook (prevents infinite agent deadlocks, max 3 retries).
- Content-hash / mtime caching (zero redundant CLI invocations on clean files).
- Fast failover ladder (AST/Native -> CLI Linters -> Graceful degradation).
"""
import sys
import json
import os
import subprocess
import pathlib
import ast
import shutil
import hashlib

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CACHE_DIR = pathlib.Path(".agents/.audit_cache")
MAX_STOP_ATTEMPTS = 3
TIMEOUT = 10

def get_cache_file(conv_id: str) -> pathlib.Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in conv_id if c.isalnum() or c in "-_")
    return CACHE_DIR / f"{safe_id or 'default'}.json"

def get_file_hash(filepath: str) -> str:
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""

def load_cache(cache_path: pathlib.Path) -> dict:
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if "files" not in data:
                    data = {"files": data, "stop_attempts": 0}
                return data
        except Exception:
            pass
    return {"files": {}, "stop_attempts": 0}

def save_cache(cache_path: pathlib.Path, cache: dict):
    if cache.get("files"):
        cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    else:
        cache_path.unlink(missing_ok=True)

def run_cmd(cmd: list[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=(os.name == "nt")
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=f"Timeout after {timeout}s")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=str(e))

def parse_tool_args(args: dict) -> str | None:
    possible_keys = [
        "TargetFile", "target_file", "file_path", "filePath", "path", "file", "filename"
    ]
    for key in possible_keys:
        val = args.get(key)
        if val and isinstance(val, str):
            return os.path.abspath(val)
    if "file" in args and isinstance(args["file"], dict):
        for key in possible_keys:
            val = args["file"].get(key)
            if val and isinstance(val, str):
                return os.path.abspath(val)
    return None

def audit_python(filepath: str) -> list[str]:
    # 1. Stdlib AST syntax check (0ms, 100% reliable)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            ast.parse(f.read(), filename=filepath)
    except SyntaxError as e:
        return [f"[Python SyntaxError] {filepath}:{e.lineno}:{e.offset}: {e.msg}"]
    except Exception as e:
        return [f"[Python ReadError] {filepath}: {e}"]

    # 2. Fast CLI Linter if available
    if shutil.which("ruff"):
        res = run_cmd(["ruff", "check", "--select=E,F", "--output-format=concise", filepath])
        if res.returncode != 0 and res.stdout.strip():
            lines = [l for l in res.stdout.splitlines() if ":" in l and not l.startswith("Found")]
            return lines[:5]
    elif shutil.which("pyright"):
        res = run_cmd(["pyright", "--outputjson", filepath])
        if res.stdout:
            try:
                data = json.loads(res.stdout)
                errors = []
                for diag in data.get("generalDiagnostics", [])[:5]:
                    if diag.get("severity") == "error":
                        r = diag.get("range", {}).get("start", {})
                        errors.append(
                            f"[Pyright Error] {filepath}:{r.get('line', 0)+1}:{r.get('character', 0)+1}: {diag.get('message')}"
                        )
                if errors:
                    return errors
            except Exception:
                pass
    return []

def audit_typescript_javascript(filepath: str) -> list[str]:
    ext = os.path.splitext(filepath)[1].lower()
    # 1. Node check for pure JS
    if ext in (".js", ".mjs", ".cjs") and shutil.which("node"):
        res = run_cmd(["node", "--check", filepath])
        if res.returncode != 0 and res.stderr:
            return [f"[JS SyntaxError] {res.stderr.strip().splitlines()[-1]}"]

    # 2. Biome / tsc
    has_biome = shutil.which("biome") is not None or os.path.exists("node_modules/.bin/biome") or os.path.exists("node_modules/.bin/biome.cmd")
    has_tsc = shutil.which("tsc") is not None or os.path.exists("node_modules/.bin/tsc") or os.path.exists("node_modules/.bin/tsc.cmd")

    if has_biome:
        cmd = ["npx", "biome", "lint", filepath] if not shutil.which("biome") else ["biome", "lint", filepath]
        res = run_cmd(cmd)
        if res.returncode != 0:
            return [f"[Biome Lint] Issues found in {filepath}. Run `biome check` for details."]
    elif has_tsc:
        cmd = ["npx", "tsc", "--noEmit"] if not shutil.which("tsc") else ["tsc", "--noEmit"]
        res = run_cmd(cmd)
        if res.returncode != 0 and res.stdout:
            lines = [l for l in res.stdout.splitlines() if "error TS" in l]
            file_ts_errors = [l for l in lines if os.path.basename(filepath) in l]
            return (file_ts_errors or lines)[:5]
    return []

def audit_astro(filepath: str) -> list[str]:
    # 1. Frontmatter check (0ms)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content.startswith("---"):
            return [f"[Astro Format] {filepath}: Missing frontmatter delimiter (---)."]
    except Exception as e:
        return [f"[Astro ReadError] {filepath}: {e}"]

    # 2. CLI Astro Check
    has_astro = (
        shutil.which("astro") is not None
        or os.path.exists("node_modules/.bin/astro")
        or os.path.exists("node_modules/.bin/astro.cmd")
    )
    if has_astro:
        cmd = ["npx", "astro", "check"] if not shutil.which("astro") else ["astro", "check"]
        res = run_cmd(cmd, timeout=15)
        if res.returncode != 0:
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            lines = [l for l in output.splitlines() if "error" in l.lower() or "TS" in l]
            file_errors = [l for l in lines if os.path.basename(filepath) in l]
            return (file_errors or lines)[:5]
    return []

def audit_json(filepath: str) -> list[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        return [f"[JSON SyntaxError] {filepath}: {e}"]
    return []

def audit_file(filepath: str) -> list[str]:
    if not os.path.exists(filepath):
        return []
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".py":
        return audit_python(filepath)
    elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        return audit_typescript_javascript(filepath)
    elif ext == ".astro":
        return audit_astro(filepath)
    elif ext == ".json":
        return audit_json(filepath)
    return []

def handle_post_tool(payload: dict):
    tool_call = payload.get("toolCall", {})
    args = tool_call.get("args", {})
    target_file = parse_tool_args(args)
    conv_id = payload.get("conversationId", "default")

    if target_file and os.path.exists(target_file):
        target_abs = os.path.abspath(target_file)
        current_hash = get_file_hash(target_abs)
        cache_path = get_cache_file(conv_id)
        cache = load_cache(cache_path)

        cached_entry = cache["files"].get(target_abs)
        if cached_entry and cached_entry.get("hash") == current_hash and not cached_entry.get("errors"):
            print(json.dumps({}))
            return

        errors = audit_file(target_abs)
        if errors:
            cache["files"][target_abs] = {"errors": errors, "hash": current_hash}
        else:
            cache["files"].pop(target_abs, None)

        save_cache(cache_path, cache)

    print(json.dumps({}))

def handle_pre_invocation(payload: dict):
    conv_id = payload.get("conversationId", "default")
    cache_path = get_cache_file(conv_id)
    cache = load_cache(cache_path)

    files = cache.get("files", {})
    if files:
        all_errors = []
        for entry in files.values():
            all_errors.extend(entry.get("errors", []))

        seen = set()
        deduped = [e for e in all_errors if not (e in seen or seen.add(e))]
        if deduped:
            msg = "🚨 [LSP Diagnostics - Action Required]:\n" + "\n".join(f"- {e}" for e in deduped[:6])
            print(json.dumps({
                "injectSteps": [
                    {"ephemeralMessage": msg}
                ]
            }))
            return

    print(json.dumps({}))

def handle_stop(payload: dict):
    conv_id = payload.get("conversationId", "default")
    cache_path = get_cache_file(conv_id)
    cache = load_cache(cache_path)

    files = cache.get("files", {})
    if files:
        attempts = cache.get("stop_attempts", 0) + 1
        cache["stop_attempts"] = attempts
        save_cache(cache_path, cache)

        # Circuit Breaker: do not deadlock agent if max retries exceeded
        if attempts > MAX_STOP_ATTEMPTS:
            sys.stderr.write(
                f"[WARN] Circuit breaker triggered after {MAX_STOP_ATTEMPTS} attempts. Allowing agent to complete.\n"
            )
            print(json.dumps({}))
            return

        first_errs = []
        for entry in files.values():
            first_errs.extend(entry.get("errors", [])[:2])
            if len(first_errs) >= 2:
                break

        reason = f"Audit failed (Attempt {attempts}/{MAX_STOP_ATTEMPTS}): Unresolved errors pending: {'; '.join(first_errs)}"
        print(json.dumps({
            "decision": "continue",
            "reason": reason
        }))
        return

    print(json.dumps({}))

def main():
    if len(sys.argv) < 2:
        print(json.dumps({}))
        return
    mode = sys.argv[1]
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    if mode == "post-tool":
        handle_post_tool(payload)
    elif mode == "pre-invocation":
        handle_pre_invocation(payload)
    elif mode == "stop":
        handle_stop(payload)
    else:
        print(json.dumps({}))

if __name__ == "__main__":
    main()
