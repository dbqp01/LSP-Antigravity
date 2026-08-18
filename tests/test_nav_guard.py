import unittest
import sys
import os
import io
import json

# Add plugin folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugin", "lsp-enforcement-kit")))
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
        sug_serena = nav_guard.build_suggestion("UserService", ["serena"])
        self.assertIn("mcp__serena__find_symbol", sug_serena)

        sug_cclsp = nav_guard.build_suggestion("UserService", ["cclsp"])
        self.assertIn("mcp__cclsp__find_definition", sug_cclsp)

        sug_fallback = nav_guard.build_suggestion("UserService", [])
        self.assertIn("semantic tools", sug_fallback)

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

if __name__ == "__main__":
    unittest.main()
