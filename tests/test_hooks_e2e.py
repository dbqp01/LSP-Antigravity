import unittest
import tempfile
import pathlib
import json
import os
import sys
import io
import shutil

# Add src folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import lsp_audit

class TestHooksE2E(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.conv_id = "test-conv-lifecycle"
        lsp_audit.CACHE_DIR = pathlib.Path(self.test_dir) / ".audit_cache"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_lifecycle_and_cache_purge(self):
        file_a = os.path.join(self.test_dir, "script_a.py")
        file_b = os.path.join(self.test_dir, "script_b.py")

        norm_a = lsp_audit.normalize_path(file_a)
        norm_b = lsp_audit.normalize_path(file_b)

        # 1. Agente escribe script_a con error
        with open(file_a, "w", encoding="utf-8") as f:
            f.write("def broken(:\n    pass\n")

        # Disparar PostToolUse para file_a
        lsp_audit.handle_post_tool({
            "conversationId": self.conv_id,
            "toolCall": {"args": {"TargetFile": file_a}}
        })

        cache = lsp_audit.load_cache(lsp_audit.get_cache_file(self.conv_id))
        self.assertIn(norm_a, cache["files"])

        # 2. Agente escribe script_b con error
        with open(file_b, "w", encoding="utf-8") as f:
            f.write("def broken_b(:\n    pass\n")

        lsp_audit.handle_post_tool({
            "conversationId": self.conv_id,
            "toolCall": {"args": {"TargetFile": file_b}}
        })

        cache = lsp_audit.load_cache(lsp_audit.get_cache_file(self.conv_id))
        self.assertEqual(len(cache["files"]), 2)

        # 3. PreInvocation inyecta mensaje efimero consolidado
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            lsp_audit.handle_pre_invocation({"conversationId": self.conv_id})
            res = json.loads(sys.stdout.getvalue())
            self.assertIn("injectSteps", res)
            ephemeral = res["injectSteps"][0]["ephemeralMessage"]
            self.assertIn("LSP Diagnostics", ephemeral)
        finally:
            sys.stdout = old_stdout

        # 4. Stop hook bloquea parada
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            lsp_audit.handle_stop({"conversationId": self.conv_id})
            res = json.loads(sys.stdout.getvalue())
            self.assertEqual(res.get("decision"), "continue")
        finally:
            sys.stdout = old_stdout

        # 5. Agente arregla script_a
        with open(file_a, "w", encoding="utf-8") as f:
            f.write("def broken():\n    pass\n")

        lsp_audit.handle_post_tool({
            "conversationId": self.conv_id,
            "toolCall": {"args": {"TargetFile": file_a}}
        })

        cache = lsp_audit.load_cache(lsp_audit.get_cache_file(self.conv_id))
        self.assertNotIn(norm_a, cache["files"])
        self.assertIn(norm_b, cache["files"])

        # 6. Agente arregla script_b
        with open(file_b, "w", encoding="utf-8") as f:
            f.write("def broken_b():\n    pass\n")

        lsp_audit.handle_post_tool({
            "conversationId": self.conv_id,
            "toolCall": {"args": {"TargetFile": file_b}}
        })

        cache = lsp_audit.load_cache(lsp_audit.get_cache_file(self.conv_id))
        self.assertEqual(len(cache.get("files", {})), 0)

        # 7. PreInvocation y Stop ahora pasan limpios
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            lsp_audit.handle_pre_invocation({"conversationId": self.conv_id})
            self.assertEqual(json.loads(sys.stdout.getvalue()), {})
        finally:
            sys.stdout = old_stdout

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            lsp_audit.handle_stop({"conversationId": self.conv_id})
            self.assertEqual(json.loads(sys.stdout.getvalue()), {})
        finally:
            sys.stdout = old_stdout

if __name__ == "__main__":
    unittest.main()
