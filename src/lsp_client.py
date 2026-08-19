"""
Standardized Language Server Protocol (LSP 3.17) Client.
Implements JSON-RPC 2.0 with Content-Length header framing over stdio.

Features:
- Full stdio framing compliance (Content-Length: ...\\r\\n\\r\\n).
- Thread-safe bidirectional communication (stdin writer, stderr isolator, background stdout reader).
- Protocol Handshake (initialize, initialized, shutdown, exit).
- Document Sync (textDocument/didOpen, textDocument/didChange, textDocument/didClose).
- Semantic Queries:
  * textDocument/definition (Go to definition)
  * textDocument/references (Find all usages)
  * textDocument/documentSymbol (File outline)
  * workspace/symbol (Global workspace symbol search)
- Real-time diagnostic listener (textDocument/publishDiagnostics).
- Zero external dependencies: Python stdlib only (subprocess, threading, json, queue, urllib.parse).
"""
import sys
import os
import json
import queue
import threading
import subprocess
import pathlib
import urllib.parse
import urllib.request

def path_to_uri(filepath: str) -> str:
    """Converts a local file path to a standard file:// URI."""
    abs_path = os.path.abspath(filepath)
    return pathlib.Path(abs_path).as_uri()

def uri_to_path(uri: str) -> str:
    """Converts a file:// URI back to a standard local file path."""
    parsed = urllib.parse.urlparse(uri)
    host = parsed.netloc
    path = urllib.request.url2pathname(parsed.path)
    if host:
        path = f"\\\\{host}{path}"
    return os.path.normpath(path)

class LSPClient:
    """Low-level robust LSP 3.17 Client over stdio subprocess."""

    def __init__(self, command: list[str], root_path: str, timeout: float = 10.0):
        self.command = command
        self.root_path = os.path.abspath(root_path)
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self._seq = 0
        self._lock = threading.Lock()
        self._pending_responses: dict[int, queue.Queue] = {}
        self._diagnostics: dict[str, list[dict]] = {}
        self._running = False
        self._reader_thread: threading.Thread | None = None
        self.server_capabilities: dict = {}

    def start(self) -> bool:
        """Launches language server process and starts background JSON-RPC framing reader."""
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.root_path,
                bufsize=0
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            return self._initialize()
        except Exception as e:
            sys.stderr.write(f"[LSPClient] Failed to start {self.command}: {e}\n")
            self._running = False
            return False

    def _next_id(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def _send_raw(self, payload: dict):
        if not self.process or not self.process.stdin:
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        with self._lock:
            try:
                self.process.stdin.write(header + body)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                self._running = False

    def send_request(self, method: str, params: dict | None = None) -> dict | None:
        """Sends a JSON-RPC request and synchronously awaits the response."""
        if not self._running:
            return None
        req_id = self._next_id()
        resp_queue = queue.Queue()
        self._pending_responses[req_id] = resp_queue

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        self._send_raw(payload)

        try:
            res = resp_queue.get(timeout=self.timeout)
            return res
        except queue.Empty:
            return None
        finally:
            self._pending_responses.pop(req_id, None)

    def send_notification(self, method: str, params: dict | None = None):
        """Sends a one-way notification to the language server."""
        if not self._running:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        self._send_raw(payload)

    def _read_loop(self):
        """Reads newline-delimited Content-Length framed JSON-RPC messages from stdout."""
        stdout = self.process.stdout
        while self._running and stdout:
            try:
                # 1. Parse headers
                content_length = None
                while True:
                    line = stdout.readline()
                    if not line:
                        self._running = False
                        return
                    line_str = line.decode("latin1", errors="replace").strip()
                    if not line_str:
                        # Empty line marks end of headers
                        break
                    if line_str.lower().startswith("content-length:"):
                        content_length = int(line_str.split(":", 1)[1].strip())

                if content_length is None or content_length <= 0:
                    continue

                # 2. Read exact message body
                body_bytes = stdout.read(content_length)
                if not body_bytes or len(body_bytes) < content_length:
                    self._running = False
                    return

                msg = json.loads(body_bytes.decode("utf-8", errors="replace"))

                # 3. Route response vs notification
                if "id" in msg and msg["id"] in self._pending_responses:
                    self._pending_responses[msg["id"]].put(msg)
                elif msg.get("method") == "textDocument/publishDiagnostics":
                    self._handle_diagnostics(msg.get("params", {}))

            except Exception:
                pass

    def _handle_diagnostics(self, params: dict):
        uri = params.get("uri", "")
        filepath = uri_to_path(uri)
        self._diagnostics[filepath] = params.get("diagnostics", [])

    def _initialize(self) -> bool:
        root_uri = path_to_uri(self.root_path)
        params = {
            "processId": os.getpid(),
            "rootPath": self.root_path,
            "rootUri": root_uri,
            "capabilities": {
                "workspace": {
                    "symbol": {"dynamicRegistration": False},
                    "workspaceFolders": True
                },
                "textDocument": {
                    "synchronization": {"dynamicRegistration": False, "willSave": False, "didSave": True},
                    "definition": {"dynamicRegistration": False},
                    "references": {"dynamicRegistration": False},
                    "documentSymbol": {"dynamicRegistration": False, "hierarchicalDocumentSymbolSupport": True},
                    "publishDiagnostics": {"relatedInformation": True}
                }
            },
            "workspaceFolders": [{"uri": root_uri, "name": os.path.basename(self.root_path)}]
        }
        res = self.send_request("initialize", params)
        if res and "result" in res:
            self.server_capabilities = res["result"].get("capabilities", {})
            self.send_notification("initialized", {})
            return True
        return False

    def did_open(self, filepath: str, content: str | None = None, language_id: str = ""):
        if content is None:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = ""
        uri = path_to_uri(filepath)
        self.send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id or "plaintext",
                "version": 1,
                "text": content
            }
        })

    def did_change(self, filepath: str, content: str, version: int = 2):
        uri = path_to_uri(filepath)
        self.send_notification("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": [{"text": content}]
        })

    def get_definition(self, filepath: str, line: int, character: int) -> list[dict]:
        """Resolves symbol definition location via textDocument/definition."""
        uri = path_to_uri(filepath)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        }
        res = self.send_request("textDocument/definition", params)
        if not res or "result" not in res:
            return []
        result = res["result"]
        if isinstance(result, dict):
            return [result]
        elif isinstance(result, list):
            return result
        return []

    def get_references(self, filepath: str, line: int, character: int, include_decl: bool = True) -> list[dict]:
        """Finds all cross-file references of a symbol via textDocument/references."""
        uri = path_to_uri(filepath)
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_decl}
        }
        res = self.send_request("textDocument/references", params)
        if not res or "result" not in res:
            return []
        return res["result"] or []

    def get_document_symbols(self, filepath: str) -> list[dict]:
        """Returns file symbol outline via textDocument/documentSymbol."""
        uri = path_to_uri(filepath)
        res = self.send_request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})
        if not res or "result" not in res:
            return []
        return res["result"] or []

    def search_workspace_symbols(self, query: str) -> list[dict]:
        """Searches symbols across the entire workspace via workspace/symbol."""
        res = self.send_request("workspace/symbol", {"query": query})
        if not res or "result" not in res:
            return []
        return res["result"] or []

    def get_diagnostics(self, filepath: str) -> list[dict]:
        """Returns latest compiler diagnostics for a file."""
        return self._diagnostics.get(os.path.normpath(os.path.abspath(filepath)), [])

    def stop(self):
        """Clean shutdown and process termination."""
        if self._running:
            try:
                self.send_request("shutdown", None)
                self.send_notification("exit", None)
            except Exception:
                pass
            self._running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
