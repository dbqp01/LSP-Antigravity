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

    def test_python_undefined_name_detection(self):
        # Exact reproduction of user case: parser.target_tag = taag (NameError)
        py_file = os.path.join(self.test_dir, "scraper_typo.py")
        code = (
            "class SimpleParser:\n"
            "    target_tag = None\n\n"
            "def scrape(tag):\n"
            "    parser = SimpleParser()\n"
            "    parser.target_tag = taag\n"
            "    return parser\n"
        )
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(code)

        errors = lsp_audit.audit_file(py_file)
        self.assertTrue(any("NameError" in e and "taag" in e for e in errors), f"Expected NameError for 'taag', got {errors}")
        self.assertTrue(any("Did you mean 'tag'?" in e for e in errors), f"Expected 'Did you mean tag', got {errors}")

        # Fix typo
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(code.replace("taag", "tag"))

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

    def test_toml_syntax_check(self):
        toml_file = os.path.join(self.test_dir, "config.toml")
        with open(toml_file, "wb") as f:
            f.write(b"key = [1, 2,")
        errors = lsp_audit.audit_file(toml_file)
        if lsp_audit.tomllib:
            self.assertTrue(any("TOML SyntaxError" in e for e in errors))

    def test_cross_file_reconciliation(self):
        file_a = os.path.join(self.test_dir, "file_a.py")
        file_b = os.path.join(self.test_dir, "file_b.py")
        with open(file_a, "w", encoding="utf-8") as f:
            f.write("def foo(): pass\n")
        with open(file_b, "w", encoding="utf-8") as f:
            f.write("def bar(:\n pass\n")

        norm_a = lsp_audit.normalize_path(file_a)
        norm_b = lsp_audit.normalize_path(file_b)

        cache = {
            "files": {
                norm_a: {"errors": ["Old error"], "hash": "123"},
                norm_b: {"errors": ["Syntax error"], "hash": "456"}
            },
            "stop_attempts": 0
        }
        lsp_audit.reconcile_cross_file_errors(cache)
        self.assertNotIn(norm_a, cache["files"])
        self.assertIn(norm_b, cache["files"])

    def test_nearest_root_discovery(self):
        subpkg = pathlib.Path(self.test_dir) / "packages" / "app"
        subpkg.mkdir(parents=True, exist_ok=True)
        (subpkg / "package.json").write_text('{"name": "app"}', encoding="utf-8")
        src_file = subpkg / "src" / "index.ts"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("console.log('hi');", encoding="utf-8")

        detected_root = lsp_audit.find_nearest_root(str(src_file), ["package.json"])
        self.assertEqual(detected_root, subpkg)

    def test_circuit_breaker_anti_deadlock(self):
        cache_path = lsp_audit.get_cache_file(self.conv_id)
        cache = {
            "files": {"dummy.py": {"errors": ["Error 1"], "hash": "abc"}},
            "stop_attempts": 0
        }
        lsp_audit.save_cache(cache_path, cache)

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

        # Circuit breaker opens
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
