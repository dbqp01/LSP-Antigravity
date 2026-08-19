"""
LSP Manager & Language Server Auto-Provisioner for Antigravity.
OpenCode-style multi-language server registry and lifecycle orchestrator.

Supported Built-in Language Servers:
- Astro (.astro): @astrojs/language-server
- TypeScript / JavaScript (.ts, .tsx, .js, .jsx, .mjs, .cjs): typescript-language-server
- Python (.py, .pyi): pyright / basedpyright
- Rust (.rs): rust-analyzer
- Go (.go): gopls
- PHP (.php): intelephense
- Shell (.sh, .bash, .zsh): bash-language-server

Features:
- Nearest project root discovery (package.json, tsconfig.json, astro.config, pyproject.toml, Cargo.toml, go.mod).
- Auto-provisioning: executes via local node_modules, global PATH, or on-demand runner (npx / uvx / python -m).
- Warm client pooling: maintains active LSP instances per root and language.
- Clean shutdown on process exit.
"""
import os
import sys
import shutil
import atexit
import pathlib
from lsp_client import LSPClient, uri_to_path

# Language server registry mapping extensions to server specifications
SERVER_REGISTRY = {
    "astro": {
        "extensions": [".astro"],
        "markers": ["astro.config.mjs", "astro.config.ts", "astro.config.js", "package.json"],
        "cmd_candidates": [
            ["npx", "@astrojs/language-server", "--stdio"],
            ["astro-ls", "--stdio"]
        ],
        "language_id": "astro"
    },
    "typescript": {
        "extensions": [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
        "markers": ["tsconfig.json", "jsconfig.json", "package.json"],
        "cmd_candidates": [
            ["typescript-language-server", "--stdio"],
            ["npx", "typescript-language-server", "--stdio"]
        ],
        "language_id": "typescript"
    },
    "python": {
        "extensions": [".py", ".pyi"],
        "markers": ["pyproject.toml", "setup.py", "requirements.txt", ".venv", "Pipfile"],
        "cmd_candidates": [
            ["pyright-langserver", "--stdio"],
            [sys.executable, "-m", "pyright", "--stdio"],
            ["basedpyright-langserver", "--stdio"],
            ["pylsp"]
        ],
        "language_id": "python"
    },
    "rust": {
        "extensions": [".rs"],
        "markers": ["Cargo.toml"],
        "cmd_candidates": [
            ["rust-analyzer"]
        ],
        "language_id": "rust"
    },
    "go": {
        "extensions": [".go"],
        "markers": ["go.mod", "go.work"],
        "cmd_candidates": [
            ["gopls"]
        ],
        "language_id": "go"
    },
    "php": {
        "extensions": [".php"],
        "markers": ["composer.json"],
        "cmd_candidates": [
            ["intelephense", "--stdio"],
            ["npx", "intelephense", "--stdio"]
        ],
        "language_id": "php"
    },
    "bash": {
        "extensions": [".sh", ".bash", ".zsh"],
        "markers": [".git"],
        "cmd_candidates": [
            ["bash-language-server", "start"],
            ["npx", "bash-language-server", "start"]
        ],
        "language_id": "shellscript"
    }
}

class LSPManager:
    """Manages active LSPClient instances and routes file requests to appropriate language servers."""

    def __init__(self):
        self._clients: dict[str, LSPClient] = {} # Key: (language_name, root_path)
        atexit.register(self.shutdown_all)

    def find_nearest_root(self, filepath: str, markers: list[str]) -> str:
        """Finds nearest ancestor directory containing any marker file or defaults to file's directory."""
        try:
            cur = pathlib.Path(filepath).resolve().parent
            for p in [cur] + list(cur.parents):
                for marker in markers:
                    if (p / marker).exists():
                        return str(p)
        except Exception:
            pass
        return os.path.dirname(os.path.abspath(filepath))

    def detect_server_spec(self, filepath: str) -> tuple[str, dict] | None:
        """Determines matching server definition for a given file extension."""
        ext = os.path.splitext(filepath)[1].lower()
        for lang, spec in SERVER_REGISTRY.items():
            if ext in spec["extensions"]:
                return lang, spec
        return None

    def _resolve_command(self, candidates: list[list[str]], root_dir: str) -> list[str] | None:
        """Finds the first runnable command from candidates (checking local node_modules first)."""
        node_bin = os.path.join(root_dir, "node_modules", ".bin")
        for cmd in candidates:
            binary = cmd[0]
            # 1. Local project node_modules check
            if os.path.exists(os.path.join(node_bin, binary)) or os.path.exists(os.path.join(node_bin, f"{binary}.cmd")):
                local_path = os.path.join(node_bin, binary)
                return [local_path] + cmd[1:]
            # 2. System PATH check
            if shutil.which(binary):
                return cmd
            # 3. Python sys.executable check
            if binary == sys.executable:
                return cmd
        return None

    def get_or_create_client(self, filepath: str) -> tuple[LSPClient | None, str]:
        """Gets existing warm LSP client or starts a new one for the target file."""
        spec_info = self.detect_server_spec(filepath)
        if not spec_info:
            return None, ""
        lang, spec = spec_info

        root_dir = self.find_nearest_root(filepath, spec["markers"])
        client_key = f"{lang}::{os.path.normcase(root_dir)}"

        if client_key in self._clients:
            client = self._clients[client_key]
            if client._running:
                return client, spec["language_id"]
            else:
                self._clients.pop(client_key, None)

        cmd = self._resolve_command(spec["cmd_candidates"], root_dir)
        if not cmd:
            return None, spec["language_id"]

        client = LSPClient(cmd, root_dir)
        if client.start():
            self._clients[client_key] = client
            return client, spec["language_id"]
        return None, spec["language_id"]

    def find_definition(self, filepath: str, line: int = 0, character: int = 0) -> list[dict]:
        client, lang_id = self.get_or_create_client(filepath)
        if not client:
            return []
        client.did_open(filepath, language_id=lang_id)
        results = client.get_definition(filepath, line, character)
        locations = []
        for r in results:
            uri = r.get("uri") or r.get("targetUri", "")
            target_range = r.get("range") or r.get("targetSelectionRange") or r.get("targetRange", {})
            if uri:
                locations.append({
                    "file": uri_to_path(uri),
                    "line": target_range.get("start", {}).get("line", 0) + 1,
                    "character": target_range.get("start", {}).get("character", 0) + 1
                })
        return locations

    def find_references(self, filepath: str, line: int = 0, character: int = 0) -> list[dict]:
        client, lang_id = self.get_or_create_client(filepath)
        if not client:
            return []
        client.did_open(filepath, language_id=lang_id)
        results = client.get_references(filepath, line, character)
        locations = []
        for r in results:
            uri = r.get("uri", "")
            target_range = r.get("range", {})
            if uri:
                locations.append({
                    "file": uri_to_path(uri),
                    "line": target_range.get("start", {}).get("line", 0) + 1,
                    "character": target_range.get("start", {}).get("character", 0) + 1
                })
        return locations

    def search_workspace_symbols(self, query: str, workspace_path: str = ".") -> list[dict]:
        """Searches symbols across all active language servers in the workspace."""
        all_symbols = []
        for client in self._clients.values():
            if client._running:
                res = client.search_workspace_symbols(query)
                for s in res:
                    loc = s.get("location", {})
                    uri = loc.get("uri", "")
                    pos = loc.get("range", {}).get("start", {})
                    all_symbols.append({
                        "name": s.get("name", ""),
                        "kind": s.get("kind", 0),
                        "file": uri_to_path(uri) if uri else "",
                        "line": pos.get("line", 0) + 1
                    })
        return all_symbols

    def get_document_outline(self, filepath: str) -> list[dict]:
        client, lang_id = self.get_or_create_client(filepath)
        if not client:
            return []
        client.did_open(filepath, language_id=lang_id)
        return client.get_document_symbols(filepath)

    def get_diagnostics(self, filepath: str) -> list[str]:
        client, lang_id = self.get_or_create_client(filepath)
        if not client:
            return []
        client.did_open(filepath, language_id=lang_id)
        raw_diags = client.get_diagnostics(filepath)
        formatted = []
        for d in raw_diags:
            line = d.get("range", {}).get("start", {}).get("line", 0) + 1
            col = d.get("range", {}).get("start", {}).get("character", 0) + 1
            msg = d.get("message", "").strip()
            severity = d.get("severity", 1)
            sev_str = "Error" if severity == 1 else "Warning"
            formatted.append(f"[{sev_str}] {filepath}:{line}:{col}: {msg}")
        return formatted

    def shutdown_all(self):
        """Cleanly terminates all active language server instances."""
        for client in list(self._clients.values()):
            try:
                client.stop()
            except Exception:
                pass
        self._clients.clear()

# Global singleton instance
GLOBAL_LSP_MANAGER = LSPManager()
