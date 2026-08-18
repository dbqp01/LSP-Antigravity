"""
Comprehensive Stress & Edge-Case Benchmark Suite for Antigravity LSP Enforcement Kit.
Tests:
1. NavGuard Pattern Strictness & Edge Cases (False Positives / False Negatives).
2. Large Files, Deep Nesting & Malformed Files (10k lines, recursion, binary fuzzing).
3. Concurrency & High Volume (50+ rapid file writes in a single session).
4. Corrupted Cache, Missing Files, and Permission Recovery.
5. Latency & Throughput Benchmark (Execution time in ms per hook invocation).
Pure ASCII compliant.
"""
import unittest
import tempfile
import pathlib
import json
import os
import sys
import time
import shutil

# Add plugin folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugin", "lsp-enforcement-kit")))
import nav_guard
import lsp_audit

class TestNavGuardStrictnessAndEdgeCases(unittest.TestCase):
    """Stress tests query pattern boundary for False Positives vs False Negatives."""

    def test_should_block_symbols(self):
        symbols_to_block = [
            "UserService", "OrderRepository", "ApiClient", "AuthProvider",
            "getUserById", "handleSubmit", "calculateTotal", "fetchData",
            "write_audit_log", "get_user_profile", "parse_json_payload",
            "User.find", "auth.login", "router.push", "db.query", "config.get",
            "IUserService", "TUserData", "HTMLParser", "PaymentGatewayService"
        ]
        for sym in symbols_to_block:
            is_sym, kind = nav_guard.is_code_symbol(sym)
            self.assertTrue(is_sym, f"Expected '{sym}' to be detected as code symbol, got '{kind}'")

    def test_should_allow_general_queries(self):
        queries_to_allow = [
            "TODO", "FIXME", "NOTE: remember to review", "BUG in auth",
            "*.ts", "*.py", "*.json", "*.astro", "*.rs",
            "https://api.github.com/v1", "http://localhost:3000",
            "--verbose", "--dry-run", "-v", "--no-emit",
            "port=8080", "NODE_ENV=production",
            "src/utils/file.ts", "lib/app.py",
            "how to handle auth state in react",
            "search for text in documentation",
            "README", "CHANGELOG", "LICENSE",
            "" # empty query
        ]
        for query in queries_to_allow:
            is_sym, kind = nav_guard.is_code_symbol(query)
            self.assertFalse(is_sym, f"Expected '{query}' to be allowed, but was blocked as '{kind}'")

    def test_massive_and_fuzzed_queries(self):
        # 100KB query string
        huge_query = "a" * 100000
        is_sym, _ = nav_guard.is_code_symbol(huge_query)
        self.assertFalse(is_sym)

        # Fuzz special characters
        fuzz_queries = ["@#$%^&*()", "SELECT * FROM users WHERE id = 1", "<div className='app'>", "&& || != =="]
        for f in fuzz_queries:
            # None of these should crash
            nav_guard.is_code_symbol(f)


class TestAuditEngineStressAndResilience(unittest.TestCase):
    """Stress tests AST, caching, corrupted environments and file scaling."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.conv_id = "stress-session-001"
        lsp_audit.CACHE_DIR = pathlib.Path(self.test_dir) / ".audit_cache"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_large_python_file_10k_lines(self):
        large_py = os.path.join(self.test_dir, "large_10k.py")
        with open(large_py, "w", encoding="utf-8") as f:
            for i in range(10000):
                f.write(f"def func_{i}():\n    return {i} * 2\n")

        start = time.perf_counter()
        errors = lsp_audit.audit_file(large_py)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(len(errors), 0)
        self.assertLess(duration_ms, 250, f"10k lines AST audit took too long: {duration_ms:.2f}ms")

    def test_error_capping_500_syntax_errors(self):
        broken_py = os.path.join(self.test_dir, "broken_500.py")
        with open(broken_py, "w", encoding="utf-8") as f:
            for i in range(500):
                f.write(f"def broken_{i}(:\n    pass\n")

        errors = lsp_audit.audit_file(broken_py)
        self.assertTrue(len(errors) > 0)
        # Verify capped to at most 5 errors to protect LLM context window
        self.assertLessEqual(len(errors), 5, f"Expected capped errors <= 5, got {len(errors)}")

    def test_deep_nesting_stress(self):
        deep_json = os.path.join(self.test_dir, "deep.json")
        # 100 levels of valid nesting: {"k": {"k": ... {"val": 1} ...}}
        obj = {"val": 1}
        for _ in range(100):
            obj = {"k": obj}
        with open(deep_json, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj))

        errors = lsp_audit.audit_file(deep_json)
        self.assertEqual(len(errors), 0)

    def test_high_volume_concurrency_simulation(self):
        # Simulate 50 rapid file modifications in a single session
        files = []
        for i in range(50):
            p = os.path.join(self.test_dir, f"module_{i}.py")
            with open(p, "w", encoding="utf-8") as f:
                if i % 5 == 0:
                    f.write("def broken(:\n    pass\n") # 10 files with errors
                else:
                    f.write(f"def valid_{i}():\n    return {i}\n")
            files.append(p)

        start = time.perf_counter()
        for p in files:
            lsp_audit.handle_post_tool({
                "conversationId": self.conv_id,
                "toolCall": {"args": {"TargetFile": p}}
            })
        total_duration_ms = (time.perf_counter() - start) * 1000

        cache = lsp_audit.load_cache(lsp_audit.get_cache_file(self.conv_id))
        self.assertEqual(len(cache["files"]), 10, "Expected exactly 10 broken files in cache")
        avg_ms_per_file = total_duration_ms / 50
        print(f"\n  [BENCHMARK] 50 rapid file audits: {total_duration_ms:.2f}ms total (Avg: {avg_ms_per_file:.2f}ms/file)")
        self.assertLess(avg_ms_per_file, 30, f"Average audit per file took too long: {avg_ms_per_file:.2f}ms")

    def test_corrupted_cache_recovery(self):
        cache_file = lsp_audit.get_cache_file(self.conv_id)
        cache_file.write_text("{CORRUPTED_JSON_RAW_DATA_1234%", encoding="utf-8")

        recovered = lsp_audit.load_cache(cache_file)
        self.assertEqual(recovered, {"files": {}, "stop_attempts": 0})

    def test_nonexistent_file_handling(self):
        errors = lsp_audit.audit_file(os.path.join(self.test_dir, "ghost_file.py"))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
