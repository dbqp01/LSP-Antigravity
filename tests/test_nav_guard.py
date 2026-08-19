import unittest
import sys
import os
import io
import json

# Add src folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import nav_guard

class TestNavGuard(unittest.TestCase):
    def test_code_symbol_detection(self):
        # PascalCase symbols
        self.assertTrue(nav_guard.is_code_symbol("UserService")[0])
        self.assertTrue(nav_guard.is_code_symbol("CardComponent")[0])

        # camelCase methods / variables
        self.assertTrue(nav_guard.is_code_symbol("getUserById")[0])
        self.assertTrue(nav_guard.is_code_symbol("handleSubmit")[0])

        # snake_case functions
        self.assertTrue(nav_guard.is_code_symbol("write_audit_log")[0])
        self.assertTrue(nav_guard.is_code_symbol("get_user_info")[0])

        # Member access
        self.assertTrue(nav_guard.is_code_symbol("AuthService.login")[0])
        self.assertTrue(nav_guard.is_code_symbol("router.refresh")[0])

    def test_allowed_patterns(self):
        # Comments / keywords
        self.assertFalse(nav_guard.is_code_symbol("TODO")[0])
        self.assertFalse(nav_guard.is_code_symbol("FIXME: investigate bug")[0])

        # Glob file extensions
        self.assertFalse(nav_guard.is_code_symbol("*.ts")[0])
        self.assertFalse(nav_guard.is_code_symbol("*.astro")[0])

        # Multi-word search
        self.assertFalse(nav_guard.is_code_symbol("how to authenticate user")[0])

    def test_provider_suggestions(self):
        sug_native = nav_guard.build_suggestion("UserService", [])
        self.assertIn("mcp__lsp-enforcement-kit__find_definition", sug_native)

        sug_serena = nav_guard.build_suggestion("UserService", ["serena"])
        self.assertIn("mcp__serena__find_symbol", sug_serena)

        sug_cclsp = nav_guard.build_suggestion("UserService", ["cclsp"])
        self.assertIn("mcp__cclsp__find_definition", sug_cclsp)

    def test_handle_pre_tool_block(self):
        payload = {
            "conversationId": "test-123",
            "toolCall": {
                "name": "grep_search",
                "args": {"Query": "UserService"}
            }
        }
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            nav_guard.handle_pre_tool(payload)
            output = json.loads(sys.stdout.getvalue())
            self.assertEqual(output.get("decision"), "deny")
            self.assertIn("LSP-FIRST GUARD", output.get("reason", ""))
        finally:
            sys.stdout = old_stdout

    def test_handle_pre_tool_allow(self):
        payload = {
            "conversationId": "test-123",
            "toolCall": {
                "name": "grep_search",
                "args": {"Query": "TODO: fix memory leak"}
            }
        }
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            nav_guard.handle_pre_tool(payload)
            output = json.loads(sys.stdout.getvalue())
            self.assertEqual(output.get("decision"), "allow")
        finally:
            sys.stdout = old_stdout

    def test_handle_pre_tool_run_command_shell_blocking(self):
        # Shell grep for symbol
        payload = {
            "conversationId": "test-123",
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "grep -rn \"UserService\" ./src"}
            }
        }
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            nav_guard.handle_pre_tool(payload)
            output = json.loads(sys.stdout.getvalue())
            self.assertEqual(output.get("decision"), "deny")
            self.assertIn("LSP-FIRST GUARD", output.get("reason", ""))
        finally:
            sys.stdout = old_stdout

        # PowerShell Get-ChildItem with code symbol filter
        payload_ps = {
            "conversationId": "test-123",
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "Get-ChildItem -Path . -Recurse -Filter \"*calculateTotal*\""}
            }
        }
        sys.stdout = io.StringIO()
        try:
            nav_guard.handle_pre_tool(payload_ps)
            output = json.loads(sys.stdout.getvalue())
            self.assertEqual(output.get("decision"), "deny")
        finally:
            sys.stdout = old_stdout

        # General non-symbol command allowed
        payload_normal = {
            "conversationId": "test-123",
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "Get-ChildItem -Path C:\\Users\\akim\\.gemini -Recurse -Filter \"*market*\""}
            }
        }
        sys.stdout = io.StringIO()
        try:
            nav_guard.handle_pre_tool(payload_normal)
            output = json.loads(sys.stdout.getvalue())
            self.assertEqual(output.get("decision"), "allow")
        finally:
            sys.stdout = old_stdout

if __name__ == "__main__":
    unittest.main()
