import unittest
import tempfile
import pathlib
import json
import os
import sys
import io
import shutil

# Add plugin folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugin", "lsp-enforcement-kit")))
import lsp_audit

class TestAuditEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.conv_id = "test-conv-e2e"
        lsp_audit.CACHE_DIR = pathlib.Path(self.test_dir) / ".audit_cache"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_python_syntax_and_recovery(self):
        py_file = os.path.join(self.test_dir, "bad.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("def foo(:\n    pass\n")
        errors = lsp_audit.audit_file(py_file)
        self.assertTrue(any("SyntaxError" in e for e in errors))

        # Fix syntax
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("def foo():\n    pass\n")
        errors_fixed = lsp_audit.audit_file(py_file)
        self.assertEqual(len(errors_fixed), 0)

    def test_astro_frontmatter_check(self):
        astro_file = os.path.join(self.test_dir, "page.astro")
        with open(astro_file, "w", encoding="utf-8") as f:
            f.write("<div>No frontmatter delimiter</div>")
        errors = lsp_audit.audit_file(astro_file)
        self.assertTrue(any("Missing frontmatter" in e for e in errors))

        # Fix frontmatter
        with open(astro_file, "w", encoding="utf-8") as f:
            f.write("---\nconst title = 'Test';\n---\n<div>Valid</div>")
        errors_fixed = lsp_audit.audit_file(astro_file)
        self.assertEqual(len(errors_fixed), 0)

    def test_json_syntax_check(self):
        json_file = os.path.join(self.test_dir, "data.json")
        with open(json_file, "w", encoding="utf-8") as f:
            f.write('{"key": "value",}')
        errors = lsp_audit.audit_file(json_file)
        self.assertTrue(any("JSON SyntaxError" in e for e in errors))

    def test_circuit_breaker_anti_deadlock(self):
        cache_path = lsp_audit.get_cache_file(self.conv_id)
        cache = {
            "files": {"dummy.py": {"errors": ["Error 1"], "hash": "abc"}},
            "stop_attempts": 0
        }
        lsp_audit.save_cache(cache_path, cache)

        # 1. First 3 stop attempts should block with 'continue'
        for attempt in range(1, lsp_audit.MAX_STOP_ATTEMPTS + 1):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                lsp_audit.handle_stop({"conversationId": self.conv_id})
                output = json.loads(sys.stdout.getvalue())
                self.assertEqual(output.get("decision"), "continue")
                self.assertIn(f"Attempt {attempt}/{lsp_audit.MAX_STOP_ATTEMPTS}", output.get("reason", ""))
            finally:
                sys.stdout = old_stdout

        # 2. 4th attempt exceeds threshold -> circuit breaker opens (returns empty dict, allowing stop)
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            lsp_audit.handle_stop({"conversationId": self.conv_id})
            output = json.loads(sys.stdout.getvalue())
            self.assertNotIn("decision", output)
            self.assertEqual(output, {})
        finally:
            sys.stdout = old_stdout

if __name__ == "__main__":
    unittest.main()
