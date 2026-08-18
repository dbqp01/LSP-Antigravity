"""
LSP/ACP Post-Write Code Auditor & Quality Gate for Antigravity CLI.
Ponytail (ULTRA) Production Architecture:
- Python stdlib only (zero pip dependencies).
- Pure ASCII standard compliance (no unicode emojis in outputs).
- Built-in Semantic Scope & Undefined Name Resolution (symtable + difflib):
  Catches NameError typos (e.g. 'taag' vs 'tag') statically in 0ms without external linters.
- Python Module Invocation Fallback (sys.executable -m ruff/pyright):
  Detects tools even if Python's Scripts/ directory is missing from system PATH.
- Nearest-Root Discovery (Scales seamlessly in monorepos by isolating subpackages).
- Cross-platform path normalization (Windows/macOS/Linux case & separator consistency).
- Multi-language support: Python, TypeScript, JavaScript, Astro, Rust, Go, JSON, TOML.
- Cross-file reconciliation: Re-checks failing files in session after shared fixes.
- Circuit breaker on Stop hook (prevents infinite agent deadlocks, max 3 retries).
- Content-hash caching (zero redundant CLI invocations on clean files).
- Fast failover ladder (AST/Symtable -> CLI Linters -> Graceful degradation).
- Built-in status diagnostics mode (status).
"""
import sys
import json
import os
import subprocess
import pathlib
import ast
import shutil
import hashlib
import builtins
import difflib
import symtable

# Python 3.11+ TOML support in stdlib
try:
    import tomllib
except ImportError:
    tomllib = None

CACHE_DIR = pathlib.Path(".agents/.audit_cache")
MAX_STOP_ATTEMPTS = 3
TIMEOUT = 10

def normalize_path(filepath: str) -> str:
    """Normalizes path casing and separators for robust cross-platform comparison."""
    if not filepath:
        return ""
    abs_path = os.path.abspath(filepath)
    return os.path.normcase(abs_path) if os.name == "nt" else abs_path

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

def run_cmd(cmd: list[str], cwd: str | None = None, timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=(os.name == "nt")
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=f"Timeout after {timeout}s")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=str(e))

def find_nearest_root(filepath: str, markers: list[str]) -> pathlib.Path | None:
    """Finds nearest ancestor directory containing any of the marker files."""
    try:
        cur = pathlib.Path(filepath).resolve().parent
        for p in [cur] + list(cur.parents):
            for marker in markers:
                if (p / marker).exists():
                    return p
    except Exception:
        pass
    return None

def get_python_tool_cmd(tool_name: str) -> list[str] | None:
    """Resolves Python linters directly or via python -m fallback."""
    if shutil.which(tool_name):
        return [tool_name]
    try:
        res = subprocess.run([sys.executable, "-m", tool_name, "--version"], capture_output=True, timeout=2)
        if res.returncode == 0:
            return [sys.executable, "-m", tool_name]
    except Exception:
        pass
    return None

def parse_tool_args(args: dict) -> str | None:
    possible_keys = [
        "TargetFile", "target_file", "file_path", "filePath", "path", "file", "filename"
    ]
    for key in possible_keys:
        val = args.get(key)
        if val and isinstance(val, str):
            return normalize_path(val)
    if "file" in args and isinstance(args["file"], dict):
        for key in possible_keys:
            val = args["file"].get(key)
            if val and isinstance(val, str):
                return normalize_path(val)
    return None

def audit_python_scope_symbols(source: str, filepath: str) -> list[str]:
    """Statically resolves local/global symbol tables to catch NameErrors (undefined variables) in O(N)."""
    if source.count("\n") > 3000:
        return []

    built_in_names = set(dir(builtins))
    try:
        table = symtable.symtable(source, filepath, "exec")
    except Exception:
        return []

    global_assigned = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported()}
    base_available = global_assigned | built_in_names

    errors = []
    stack = [table]
    while stack:
        scope = stack.pop()
        for s in scope.get_symbols():
            name = s.get_name()
            # If variable is referenced as global but not defined globally or in builtins
            if s.is_global() and not s.is_local() and not s.is_imported() and not s.is_assigned():
                if name not in global_assigned and name not in built_in_names and not name.startswith("__"):
                    local_names = {sym.get_name() for sym in scope.get_symbols() if sym.is_local() or sym.is_assigned()}
                    available = list(base_available | local_names)
                    close = difflib.get_close_matches(name, available, n=1, cutoff=0.6)
                    hint = f" (Did you mean '{close[0]}'?) " if close else ""
                    errors.append(f"[Python NameError] {filepath}: Undefined name '{name}'{hint}")
                    if len(errors) >= 5:
                        return errors

        stack.extend(scope.get_children())

    return errors

def audit_python(filepath: str) -> list[str]:
    # 1. AST syntax check (0ms, 100% reliable)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return [f"[Python SyntaxError] {filepath}:{e.lineno}:{e.offset}: {e.msg}"]
    except Exception as e:
        return [f"[Python ReadError] {filepath}: {e}"]

    # 2. Built-in Scope & Symbol Table Resolution (Catches NameError/undefined variables in < 2ms)
    scope_errors = audit_python_scope_symbols(content, filepath)
    if scope_errors:
        return scope_errors

    # 3. Fast CLI Linter if available (Ruff / Pyright with python -m fallback)
    ruff_cmd = get_python_tool_cmd("ruff")
    if ruff_cmd:
        res = run_cmd(ruff_cmd + ["check", "--select=E,F", "--output-format=concise", filepath])
        if res.returncode != 0 and res.stdout.strip():
            lines = [l for l in res.stdout.splitlines() if ":" in l and not l.startswith("Found")]
            return lines[:5]
    else:
        pyright_cmd = get_python_tool_cmd("pyright")
        if pyright_cmd:
            py_root = find_nearest_root(filepath, ["pyproject.toml", "setup.py", "requirements.txt"])
            cwd = str(py_root) if py_root else None
            res = run_cmd(pyright_cmd + ["--outputjson", filepath], cwd=cwd)
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

    ts_root = find_nearest_root(filepath, ["tsconfig.json", "package.json"])
    if not ts_root:
        return []
    cwd = str(ts_root)

    has_biome = shutil.which("biome") is not None or (ts_root / "node_modules/.bin/biome").exists()
    has_tsc = shutil.which("tsc") is not None or (ts_root / "node_modules/.bin/tsc").exists()

    if has_biome:
        cmd = ["npx", "biome", "lint", filepath] if not shutil.which("biome") else ["biome", "lint", filepath]
        res = run_cmd(cmd, cwd=cwd)
        if res.returncode != 0:
            return [f"[Biome Lint] Issues found in {filepath}."]
    elif has_tsc:
        cmd = ["npx", "tsc", "--noEmit"] if not shutil.which("tsc") else ["tsc", "--noEmit"]
        res = run_cmd(cmd, cwd=cwd)
        if res.returncode != 0 and res.stdout:
            lines = [l for l in res.stdout.splitlines() if "error TS" in l]
            file_ts_errors = [l for l in lines if os.path.basename(filepath) in l]
            return (file_ts_errors or lines)[:5]
    return []

def audit_astro(filepath: str) -> list[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content.startswith("---"):
            return [f"[Astro Format] {filepath}: Missing frontmatter delimiter (---)."]
    except Exception as e:
        return [f"[Astro ReadError] {filepath}: {e}"]

    astro_root = find_nearest_root(filepath, ["astro.config.mjs", "astro.config.ts", "package.json"])
    if not astro_root:
        return []
    cwd = str(astro_root)

    has_astro = (
        shutil.which("astro") is not None
        or (astro_root / "node_modules/.bin/astro").exists()
    )
    if has_astro:
        cmd = ["npx", "astro", "check"] if not shutil.which("astro") else ["astro", "check"]
        res = run_cmd(cmd, cwd=cwd, timeout=15)
        if res.returncode != 0:
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            lines = [l for l in output.splitlines() if "error" in l.lower() or "TS" in l]
            file_errors = [l for l in lines if os.path.basename(filepath) in l]
            return (file_errors or lines)[:5]
    return []

def audit_rust(filepath: str) -> list[str]:
    if shutil.which("cargo"):
        cargo_root = find_nearest_root(filepath, ["Cargo.toml"])
        if cargo_root:
            res = run_cmd(["cargo", "check", "--message-format=json"], cwd=str(cargo_root), timeout=15)
            if res.returncode != 0 and res.stdout:
                errors = []
                for line in res.stdout.splitlines():
                    try:
                        msg = json.loads(line)
                        if msg.get("reason") == "compiler-message":
                            diag = msg.get("message", {})
                            if diag.get("level") == "error":
                                rendered = diag.get("rendered", "").splitlines()
                                if rendered:
                                    errors.append(f"[Rust Error] {rendered[0]}")
                    except Exception:
                        pass
                return errors[:5]
    return []

def audit_go(filepath: str) -> list[str]:
    if shutil.which("go"):
        go_root = find_nearest_root(filepath, ["go.mod"])
        if not go_root:
            return []
        cwd = str(go_root)
        res = run_cmd(["go", "vet", filepath], cwd=cwd, timeout=10)
        if res.returncode != 0 and res.stderr:
            return [f"[Go Vet] {l}" for l in res.stderr.splitlines()[:5]]
    return []

def audit_json(filepath: str) -> list[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        return [f"[JSON SyntaxError] {filepath}: {e}"]
    return []

def audit_toml(filepath: str) -> list[str]:
    if tomllib:
        try:
            with open(filepath, "rb") as f:
                tomllib.load(f)
        except Exception as e:
            return [f"[TOML SyntaxError] {filepath}: {e}"]
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
    elif ext == ".rs":
        return audit_rust(filepath)
    elif ext == ".go":
        return audit_go(filepath)
    elif ext == ".json":
        return audit_json(filepath)
    elif ext == ".toml":
        return audit_toml(filepath)
    return []

def reconcile_cross_file_errors(cache: dict) -> bool:
    """Re-checks all currently failed files to see if a recent change fixed them."""
    changed = False
    files_to_recheck = list(cache["files"].keys())
    for fpath in files_to_recheck:
        if os.path.exists(fpath):
            current_errors = audit_file(fpath)
            if not current_errors:
                cache["files"].pop(fpath, None)
                changed = True
            else:
                cache["files"][fpath]["errors"] = current_errors
                cache["files"][fpath]["hash"] = get_file_hash(fpath)
        else:
            cache["files"].pop(fpath, None)
            changed = True
    return changed

def handle_post_tool(payload: dict):
    tool_call = payload.get("toolCall", {})
    args = tool_call.get("args", {})
    target_file = parse_tool_args(args)
    conv_id = payload.get("conversationId", "default")

    if target_file and os.path.exists(target_file):
        current_hash = get_file_hash(target_file)
        cache_path = get_cache_file(conv_id)
        cache = load_cache(cache_path)

        cached_entry = cache["files"].get(target_file)
        if not (cached_entry and cached_entry.get("hash") == current_hash and not cached_entry.get("errors")):
            errors = audit_file(target_file)
            if errors:
                cache["files"][target_file] = {"errors": errors, "hash": current_hash}
            else:
                cache["files"].pop(target_file, None)
                if cache.get("files"):
                    reconcile_cross_file_errors(cache)

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
            msg = "[LSP Diagnostics - Action Required]:\n" + "\n".join(f"- {e}" for e in deduped[:6])
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

def print_status():
    """Prints diagnostic status of the environment and tools in pure ASCII."""
    print("=" * 60)
    print("Antigravity LSP Enforcement Kit - Diagnostic Status")
    print("=" * 60)
    
    linters = {
        "Python AST": "[OK] Available (stdlib)",
        "Python Symtable": "[OK] Available (stdlib - NameError static check)",
        "Ruff": "[OK] Available" if get_python_tool_cmd("ruff") else "[FAIL] Not found",
        "Pyright": "[OK] Available" if get_python_tool_cmd("pyright") else "[FAIL] Not found",
        "Node.js": "[OK] Available" if shutil.which("node") else "[FAIL] Not found",
        "TypeScript (tsc)": "[OK] Available" if shutil.which("tsc") else "[FAIL] Not found",
        "Biome": "[OK] Available" if shutil.which("biome") else "[FAIL] Not found",
        "Astro CLI": "[OK] Available" if shutil.which("astro") else "[FAIL] Not found",
        "Cargo (Rust)": "[OK] Available" if shutil.which("cargo") else "[FAIL] Not found",
        "Go": "[OK] Available" if shutil.which("go") else "[FAIL] Not found",
        "TOML Parser": "[OK] Available (stdlib)" if tomllib else "[FAIL] Not found (< Python 3.11)",
    }
    
    for tool, status in linters.items():
        print(f"  {tool:<20}: {status}")

    print("\nCache Directory:")
    if CACHE_DIR.exists():
        caches = list(CACHE_DIR.glob("*.json"))
        print(f"  Location : {CACHE_DIR.resolve()}")
        print(f"  Sessions : {len(caches)} active cache file(s)")
    else:
        print(f"  Location : {CACHE_DIR.resolve()} (Empty / Clean)")
    print("=" * 60)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({}))
        return
    mode = sys.argv[1]

    if mode == "status":
        print_status()
        return

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
