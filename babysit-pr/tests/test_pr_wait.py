import contextlib
import importlib.machinery
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pr-wait"
LOADER = importlib.machinery.SourceFileLoader("pr_wait", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
pr_wait: Any = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = pr_wait
LOADER.exec_module(pr_wait)


class RequiredChecksTests(unittest.TestCase):
    def setUp(self):
        self.original_gh = pr_wait.gh
        self.original_state_dir = pr_wait.STATE_DIR
        self.temp_dir = tempfile.TemporaryDirectory()
        pr_wait.STATE_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        pr_wait.gh = self.original_gh
        pr_wait.STATE_DIR = self.original_state_dir
        self.temp_dir.cleanup()

    def test_successful_authoritative_queries_distinguish_empty_and_configured_checks(self):
        def gh(args, allow=(0,)):
            if any("/protection" in arg for arg in args):
                raise pr_wait.GhError("HTTP 404: Branch not protected", False)
            return subprocess.CompletedProcess(args, 0, "", "")

        pr_wait.gh = gh
        empty = pr_wait.required_checks("owner/private", "main", "head-empty")
        self.assertEqual(empty.state, "KNOWN_EMPTY")
        self.assertEqual(empty.head_sha, "head-empty")

        def configured(args, allow=(0,)):
            value = "lint\n" if any("rules/branches/" in arg for arg in args) else "build\n"
            return subprocess.CompletedProcess(args, 0, value, "")

        pr_wait.gh = configured
        checks = pr_wait.required_checks("owner/private", "main", "head-configured")
        self.assertEqual(checks.state, "KNOWN_WITH_CHECKS")
        self.assertEqual(checks.names, frozenset({"lint", "build"}))

    def test_unexplained_protection_404_is_unknown(self):
        def gh(args, allow=(0,)):
            if any("rules/branches/" in arg for arg in args):
                return subprocess.CompletedProcess(args, 0, "", "")
            raise pr_wait.GhError("HTTP 404: Not Found", False)

        pr_wait.gh = gh
        required = pr_wait.required_checks("owner/private", "main", "head-404")

        self.assertEqual(required.state, "UNKNOWN")
        self.assertIn("HTTP 404", required.cause)

    def test_forbidden_rules_query_is_unknown_not_empty(self):
        def gh(args, allow=(0,)):
            raise pr_wait.GhError("HTTP 403: Resource not accessible by integration", False)

        pr_wait.gh = gh
        required = pr_wait.required_checks("owner/private", "main", "head-403")

        self.assertEqual(required.state, "UNKNOWN")
        self.assertIn("HTTP 403", required.cause)

    def test_forbidden_query_cannot_print_ready(self):
        def gh(args, allow=(0,)):
            if any("rules/branches/" in arg for arg in args):
                raise pr_wait.GhError("HTTP 403: Resource not accessible by integration", False)
            raise pr_wait.GhError("HTTP 404: Not Found", False)

        pr_wait.gh = gh
        watcher = pr_wait.Watcher("owner/private", 12, "ready", 5)
        watcher.baseline = False
        watcher.prev_snapshot = [("build", "pass")]
        watcher.fetch_pr = lambda: {
            "url": "https://github.com/owner/private/pull/12",
            "state": "OPEN",
            "headRefOid": "abc123456789",
            "baseRefName": "main",
            "mergeStateStatus": "CLEAN",
            "author": {"login": "author"},
            "viewer": "viewer",
            "comments": {"nodes": []},
            "reviews": {"nodes": []},
            "reviewThreads": {"nodes": []},
            "baseRef": {"target": {"oid": "base123456789"}},
        }
        watcher.fetch_checks = lambda: {
            "build": {"name": "build", "bucket": "pass", "link": "https://example.test/check"}
        }
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
            watcher.poll()

        self.assertEqual(stopped.exception.code, 1)
        self.assertNotIn("ready on", stdout.getvalue())
        self.assertIn("HTTP 403", stdout.getvalue() + stderr.getvalue())

    def test_head_change_during_completion_recheck_blocks_ready(self):
        def gh(args, allow=(0,)):
            if any("/protection" in arg for arg in args):
                raise pr_wait.GhError("HTTP 404: Branch not protected", False)
            return subprocess.CompletedProcess(args, 0, "", "")

        pr_wait.gh = gh
        watcher = pr_wait.Watcher("owner/private", 12, "ready", 5)
        watcher.baseline = False
        pr = {
            "url": "https://github.com/owner/private/pull/12",
            "state": "OPEN",
            "headRefOid": "old-head-sha",
            "baseRefName": "main",
            "mergeStateStatus": "CLEAN",
            "author": {"login": "author"},
            "viewer": "viewer",
            "comments": {"nodes": []},
            "reviews": {"nodes": []},
            "reviewThreads": {"nodes": []},
            "baseRef": {"target": {"oid": "base123456789"}},
        }
        current_pr = {**pr, "headRefOid": "new-head-sha"}
        replies = iter([pr, pr, current_pr])
        watcher.fetch_pr = lambda: next(replies)
        watcher.fetch_checks = lambda: {
            "build": {"name": "build", "bucket": "pass", "link": "https://example.test/check"}
        }
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            watcher.poll()
            watcher.poll()

        self.assertEqual(watcher.state["head_oid"], "new-head-sha")
        self.assertIsNone(watcher.required)
        self.assertIn("head changed", stdout.getvalue().lower())
        self.assertNotIn("ready on", stdout.getvalue())

    def test_head_change_invalidates_prior_check_snapshot(self):
        def gh(args, allow=(0,)):
            if any("/rules/branches/" in arg for arg in args):
                return subprocess.CompletedProcess(args, 0, "", "")
            raise pr_wait.GhError("HTTP 404: Branch not protected", False)

        pr_wait.gh = gh
        watcher = pr_wait.Watcher("owner/private", 12, "ready", 5)
        watcher.baseline = False
        watcher.state["head_oid"] = "old-head-sha"
        watcher.prev_snapshot = [("build", "pass")]
        watcher.fetch_pr = lambda: {
            "url": "https://github.com/owner/private/pull/12",
            "state": "OPEN",
            "headRefOid": "new-head-sha",
            "baseRefName": "main",
            "mergeStateStatus": "CLEAN",
            "author": {"login": "author"},
            "viewer": "viewer",
            "comments": {"nodes": []},
            "reviews": {"nodes": []},
            "reviewThreads": {"nodes": []},
            "baseRef": {"target": {"oid": "base123456789"}},
        }
        watcher.fetch_checks = lambda: {
            "build": {"name": "build", "bucket": "pass", "link": "https://example.test/check"}
        }
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            try:
                watcher.poll()
            except SystemExit as error:
                self.fail(f"head change reused stale checks and exited {error.code}")

        self.assertEqual(watcher.state["head_oid"], "new-head-sha")
        self.assertIn("head changed", stdout.getvalue().lower())
        self.assertNotIn("ready on", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
