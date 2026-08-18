import unittest
import tempfile
import pathlib
import json
import os
import sys
import io
import shutil
import ast

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

    def test_php_syntax_check(self):
        if shutil.which("php"):
            php_file = os.path.join(self.test_dir, "bad.php")
            with open(php_file, "w", encoding="utf-8") as f:
                f.write("<?php function broken( { echo 'hi'; }")
            errors = lsp_audit.audit_file(php_file)
            self.assertTrue(len(errors) > 0, f"Expected PHP syntax error, got {errors}")

            # Fix PHP file
            with open(php_file, "w", encoding="utf-8") as f:
                f.write("<?php function broken() { echo 'hi'; }")
            errors_fixed = lsp_audit.audit_file(php_file)
            self.assertEqual(len(errors_fixed), 0)

    def test_powershell_syntax_check(self):
        if shutil.which("powershell") or shutil.which("pwsh"):
            ps_file = os.path.join(self.test_dir, "script.ps1")
            with open(ps_file, "w", encoding="utf-8") as f:
                f.write("function test-func {\n    Write-Host 'unclosed function'\n")
            errors = lsp_audit.audit_file(ps_file)
            self.assertTrue(len(errors) > 0, f"Expected PowerShell syntax error, got {errors}")

            # Fix PowerShell script
            with open(ps_file, "w", encoding="utf-8") as f:
                f.write("function test-func {\n    Write-Host 'closed function'\n}\n")
            errors_fixed = lsp_audit.audit_file(ps_file)
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
        self.assertEqual(detected_root, subpkg.resolve())

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

    def test_python_wildcard_import_allowed(self):
        py_file = os.path.join(self.test_dir, "wildcard.py")
        code = "from math import *\nx = sqrt(16)\n"
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(code)

        tree = ast.parse(code, filename=py_file)
        errors = lsp_audit.audit_python_scope_symbols(code, py_file, tree=tree)
        self.assertEqual(errors, [], "Wildcard import should not trigger false-positive NameError")

    def test_multi_replace_file_content_arg_parsing(self):
        args = {"TargetFile": "src/components/App.tsx", "Instructions": "fix bug"}
        parsed = lsp_audit.parse_tool_args(args)
        self.assertTrue(parsed.endswith("app.tsx") or parsed.endswith("App.tsx"))

    def test_shell_syntax_check(self):
        if shutil.which("bash") or shutil.which("sh"):
            sh_file = os.path.join(self.test_dir, "bad.sh")
            with open(sh_file, "w", encoding="utf-8", newline="\n") as f:
                f.write("if [ 1 -eq 1 ]; then\n")  # Missing fi
            errors = lsp_audit.audit_shell(sh_file)
            self.assertTrue(len(errors) > 0, f"Expected shell syntax error, got {errors}")

            # Fix shell script
            with open(sh_file, "w", encoding="utf-8", newline="\n") as f:
                f.write("if [ 1 -eq 1 ]; then\n  echo 'hi'\nfi\n")
            errors_fixed = lsp_audit.audit_shell(sh_file)
            self.assertEqual(len(errors_fixed), 0)

    def test_typescript_unrelated_error_isolation(self):
        orig_which = shutil.which
        orig_run_cmd = lsp_audit.run_cmd
        try:
            class MockCompletedProcess:
                returncode = 1
                stdout = "src/other_file.ts(10,5): error TS2304: Cannot find name 'foo'.\n"
                stderr = ""

            shutil.which = lambda tool: "tsc" if tool == "tsc" else None
            lsp_audit.run_cmd = lambda *args, **kwargs: MockCompletedProcess()
            # Create a mock tsconfig and file
            ts_file = os.path.join(self.test_dir, "my_file.ts")
            (pathlib.Path(self.test_dir) / "tsconfig.json").write_text("{}", encoding="utf-8")
            with open(ts_file, "w", encoding="utf-8") as f:
                f.write("const a = 1;\n")

            # audit_typescript_javascript should NOT report error from other_file.ts
            errors = lsp_audit.audit_typescript_javascript(ts_file)
            self.assertEqual(errors, [], "Should not return errors from unrelated files")
        finally:
            shutil.which = orig_which
            lsp_audit.run_cmd = orig_run_cmd

    def test_rust_unrelated_error_isolation(self):
        orig_run_cmd = lsp_audit.run_cmd
        try:
            class MockCargoProcess:
                returncode = 1
                stdout = json.dumps({
                    "reason": "compiler-message",
                    "message": {
                        "level": "error",
                        "rendered": "error[E0425]: cannot find value `bar` in this scope",
                        "spans": [{"file_name": "src/other_crate_file.rs"}]
                    }
                })
                stderr = ""

            lsp_audit.run_cmd = lambda *args, **kwargs: MockCargoProcess()
            rs_file = os.path.join(self.test_dir, "lib.rs")
            (pathlib.Path(self.test_dir) / "Cargo.toml").write_text("[package]\nname='test'", encoding="utf-8")
            with open(rs_file, "w", encoding="utf-8") as f:
                f.write("fn foo() {}\n")

            errors = lsp_audit.audit_rust(rs_file)
            self.assertEqual(errors, [], "Should not report Rust errors from unrelated files")
        finally:
            lsp_audit.run_cmd = orig_run_cmd

if __name__ == "__main__":
    unittest.main()
