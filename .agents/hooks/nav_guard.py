"""
Pre-Tool Navigation Guard for Antigravity CLI.
Intercepts Grep / Glob calls to enforce LSP-first semantic navigation,
saving up to 80-90% of exploration tokens.

Features:
- Provider-aware: Detects MCP LSP servers (Serena, cclsp, etc.) in global/local configs.
- Smart regex detection: Blocks PascalCase, TypeScript Interfaces (IUserService),
  camelCase, snake_case functions, and method calls.
- Preserves general search: Allows keywords (TODO, FIXME), file extensions, and URLs.
- Zero dependencies: Python stdlib only, < 2ms execution.
- Pure ASCII standard output.
"""
import sys
import json
import os
import re
import pathlib

# Explicit code symbol detectors supporting Interfaces (IUser), Generics (TData), Acronyms (HTMLParser)
PASCAL_CASE = re.compile(r"^[A-Z]+[a-z0-9]+[A-Za-z0-9]*$")
CAMEL_CASE = re.compile(r"^[a-z0-9]+(?:[A-Z][a-z0-9]*)+$")
SNAKE_CASE_FUNC = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
DOTTED_ACCESS = re.compile(r"^[a-zA-Z_]\w*\.[a-zA-Z_]\w+$")

# Whitelist of patterns that should be allowed through Grep/Glob
ALLOWED_PATTERNS = [
    re.compile(r"^(TODO|FIXME|NOTE|BUG|HACK|XXX|README|CHANGELOG|LICENSE)\b", re.IGNORECASE),
    re.compile(r"^\*\.[a-zA-Z0-9]+$"),                     # *.ts, *.py
    re.compile(r"^https?://", re.IGNORECASE),               # URLs
    re.compile(r"^\-\-[a-zA-Z0-9_\-]+$"),                   # CLI flags (--verbose)
    re.compile(r"^[a-zA-Z0-9_\-]+=[a-zA-Z0-9_\-]+$"),       # key=value
    re.compile(r"^(src|dist|build|node_modules|tests?|lib|app|public)/"), # paths
]

def detect_mcp_providers() -> list[str]:
    """Detects configured LSP MCP servers in workspace or global configs."""
    providers = []
    config_paths = [
        pathlib.Path(".agents/mcp_config.json"),
        pathlib.Path("_agents/mcp_config.json"),
        pathlib.Path.home() / ".gemini" / "config" / "mcp_config.json",
        pathlib.Path.home() / ".gemini" / "antigravity-cli" / "mcp_config.json"
    ]

    for p in config_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                servers = data.get("mcpServers", {})
                for name in servers:
                    name_lower = name.lower()
                    if "serena" in name_lower:
                        providers.append("serena")
                    elif "cclsp" in name_lower or "lsp" in name_lower:
                        providers.append("cclsp")
            except Exception:
                pass

    return list(set(providers))

def is_code_symbol(query: str) -> tuple[bool, str]:
    query_str = query.strip()
    if not query_str or " " in query_str:
        return False, ""

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

def build_suggestion(symbol: str, providers: list[str]) -> str:
    suggestions = []
    if "serena" in providers:
        suggestions.append(f'mcp__serena__find_symbol("{symbol}")')
    if "cclsp" in providers:
        suggestions.append(f'mcp__cclsp__find_definition("{symbol}") / find_references("{symbol}")')
    
    if not suggestions:
        suggestions.append(f'LSP MCP semantic tools (find_definition, find_references) or targeted line-range view')

    return " | ".join(suggestions)

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
            providers = detect_mcp_providers()
            suggested_tool = build_suggestion(target_query, providers)
            reason = (
                f"[LSP-FIRST GUARD]: '{target_query}' detected as a {symbol_type}. "
                f"Use semantic tools instead of full-text search: {suggested_tool}"
            )
            print(json.dumps({
                "decision": "deny",
                "reason": reason
            }))
            return

    # Conforms strictly to PreToolUse schema
    print(json.dumps({"decision": "allow"}))

def main():
    if len(sys.argv) < 2 or sys.argv[1] != "pre-tool":
        print(json.dumps({"decision": "allow"}))
        return

    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    handle_pre_tool(payload)

if __name__ == "__main__":
    main()
