"""
Native Model Context Protocol (MCP) Server for Antigravity.
Implements JSON-RPC 2.0 stdio transport exposing standardized LSP operations to AI agents.

Exposed Tools:
1. find_definition: Resolves exact file and line where a symbol/function/variable is defined.
2. find_references: Finds all usages and callers of a symbol across the entire repository.
3. search_workspace_symbols: Searches classes, functions, and symbols globally across workspace.
4. get_document_outline: Returns the structural outline (classes, methods, variables) of a file.
5. get_diagnostics: Retrieves real-time compiler and type-checker diagnostics for a file.

Specifications:
- Stdline JSON-RPC 2.0 reader & writer on sys.stdin / sys.stdout.
- Stderr isolation (no corrupting stdout stream).
- Zero external dependencies: Python stdlib only.
"""
import sys
import json
from lsp_manager import GLOBAL_LSP_MANAGER

SERVER_NAME = "antigravity-lsp-kit"
SERVER_VERSION = "2.0.0"

TOOLS_SCHEMA = [
    {
        "name": "find_definition",
        "description": "Locates the exact definition (file and line) of a symbol, function, class, or variable using Language Server Protocol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Absolute or relative path to the file containing the symbol reference."},
                "line": {"type": "integer", "description": "0-indexed line number where the symbol occurs."},
                "character": {"type": "integer", "description": "0-indexed character offset of the symbol."}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "find_references",
        "description": "Finds all usages, call sites, and references of a symbol across the entire project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to file containing symbol."},
                "line": {"type": "integer", "description": "0-indexed line number."},
                "character": {"type": "integer", "description": "0-indexed character offset."}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "search_workspace_symbols",
        "description": "Searches for classes, functions, interfaces, and variables globally across the workspace using the active LSP index.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Symbol name or substring to search for (e.g. 'UserAccount', 'calculateTotal', 'login')."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_document_outline",
        "description": "Returns the complete structural outline (classes, methods, functions, variables) of a file in token-efficient format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the source file to inspect."}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "get_diagnostics",
        "description": "Retrieves real-time compiler, linter, and type-checker diagnostics for a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the file to audit."}
            },
            "required": ["filepath"]
        }
    }
]

def send_response(req_id, result=None, error=None):
    resp = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        resp["error"] = error
    else:
        resp["result"] = result
    out = json.dumps(resp, ensure_ascii=False)
    sys.stdout.write(out + "\n")
    sys.stdout.flush()

def handle_call_tool(tool_name: str, args: dict) -> dict:
    try:
        if tool_name == "find_definition":
            filepath = args.get("filepath", "")
            line = int(args.get("line", 0))
            char = int(args.get("character", 0))
            res = GLOBAL_LSP_MANAGER.find_definition(filepath, line, char)
            if not res:
                return {"content": [{"type": "text", "text": f"No definition found for symbol at {filepath}:{line}:{char}"}]}
            lines = [f"- {loc['file']}:{loc['line']}:{loc['character']}" for loc in res]
            return {"content": [{"type": "text", "text": "Definitions:\n" + "\n".join(lines)}]}

        elif tool_name == "find_references":
            filepath = args.get("filepath", "")
            line = int(args.get("line", 0))
            char = int(args.get("character", 0))
            res = GLOBAL_LSP_MANAGER.find_references(filepath, line, char)
            if not res:
                return {"content": [{"type": "text", "text": f"No references found for symbol at {filepath}:{line}:{char}"}]}
            lines = [f"- {loc['file']}:{loc['line']}:{loc['character']}" for loc in res]
            return {"content": [{"type": "text", "text": f"Found {len(res)} references:\n" + "\n".join(lines)}]}

        elif tool_name == "search_workspace_symbols":
            query = args.get("query", "")
            res = GLOBAL_LSP_MANAGER.search_workspace_symbols(query)
            if not res:
                return {"content": [{"type": "text", "text": f"No workspace symbols matching '{query}' found."}]}
            lines = [f"- {s['name']} (kind {s['kind']}) -> {s['file']}:{s['line']}" for s in res[:20]]
            return {"content": [{"type": "text", "text": f"Found {len(res)} matching symbols:\n" + "\n".join(lines)}]}

        elif tool_name == "get_document_outline":
            filepath = args.get("filepath", "")
            symbols = GLOBAL_LSP_MANAGER.get_document_outline(filepath)
            return {"content": [{"type": "text", "text": json.dumps(symbols, indent=2)}]}

        elif tool_name == "get_diagnostics":
            filepath = args.get("filepath", "")
            diags = GLOBAL_LSP_MANAGER.get_diagnostics(filepath)
            if not diags:
                return {"content": [{"type": "text", "text": f"No compiler/type diagnostics for {filepath} (clean)."}]}
            return {"content": [{"type": "text", "text": "Diagnostics:\n" + "\n".join(diags)}]}

        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}], "isError": True}

def main():
    sys.stderr.write(f"[{SERVER_NAME}] MCP stdio server started.\n")
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            sys.stderr.write(f"[{SERVER_NAME}] Malformed JSON: {e}\n")
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            send_response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            })

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            send_response(req_id, {
                "tools": TOOLS_SCHEMA
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            res = handle_call_tool(tool_name, tool_args)
            send_response(req_id, res)

        elif method == "ping":
            send_response(req_id, {})

        else:
            if req_id is not None:
                send_response(req_id, error={"code": -32601, "message": f"Method '{method}' not found"})

if __name__ == "__main__":
    main()
