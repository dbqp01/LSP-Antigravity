"""
Pre-Tool Navigation Guard for Antigravity CLI.
Intercepts Grep / Glob calls to enforce LSP-first semantic navigation,
saving up to 80-90% of exploration tokens.
Adheres to Ponytail (ULTRA): Python stdlib only, < 2ms execution.
"""
import sys
import json
import re

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Explicit code symbol detectors
PASCAL_CASE = re.compile(r"^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+$")
CAMEL_CASE = re.compile(r"^[a-z0-9]+(?:[A-Z][a-z0-9]+)+$")
SNAKE_CASE_FUNC = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
DOTTED_ACCESS = re.compile(r"^[a-zA-Z_]\w*\.[a-zA-Z_]\w+$")

# Whitelist of patterns that should be allowed through Grep/Glob
ALLOWED_PATTERNS = [
    re.compile(r"^(TODO|FIXME|NOTE|BUG|HACK|XXX)\b", re.IGNORECASE),
    re.compile(r"^\*\.[a-zA-Z0-9]+$"),                     # *.ts, *.py
    re.compile(r"^https?://", re.IGNORECASE),               # URLs
    re.compile(r"^\-\-[a-zA-Z0-9_\-]+$"),                   # CLI flags (--verbose)
    re.compile(r"^[a-zA-Z0-9_\-]+=[a-zA-Z0-9_\-]+$"),       # key=value
    re.compile(r"^(src|dist|build|node_modules|tests?|lib|app|public)/"), # paths
]

def is_code_symbol(query: str) -> tuple[bool, str]:
    query_str = query.strip()
    if not query_str or " " in query_str:
        return False, ""

    # Check allowlist first
    for allowed in ALLOWED_PATTERNS:
        if allowed.search(query_str):
            return False, ""

    if PASCAL_CASE.match(query_str):
        return True, "PascalCase Class/Interface"
    if CAMEL_CASE.match(query_str):
        return True, "camelCase Method/Variable"
    if SNAKE_CASE_FUNC.match(query_str):
        return True, "snake_case Function/Symbol"
    if DOTTED_ACCESS.match(query_str):
        return True, "Member/Property Access"

    return False, ""

def handle_pre_tool(payload: dict):
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    target_query = ""
    if tool_name == "grep_search":
        target_query = args.get("Query", "")
    elif tool_name == "find_by_name":
        target_query = args.get("Pattern", "").replace("*", "")

    if target_query:
        is_symbol, symbol_type = is_code_symbol(target_query)
        if is_symbol:
            reason = (
                f"⛔ [LSP-FIRST GUARD]: '{target_query}' was detected as a {symbol_type}. "
                f"Use LSP/MCP semantic navigation (find_definition, find_references, workspace_symbols) "
                f"or precise line range reading instead of whole-repo grep to save tokens."
            )
            print(json.dumps({
                "decision": "deny",
                "reason": reason
            }))
            return

    # Allow tool execution
    print(json.dumps({}))

def main():
    if len(sys.argv) < 2 or sys.argv[1] != "pre-tool":
        print(json.dumps({}))
        return

    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    handle_pre_tool(payload)

if __name__ == "__main__":
    main()
