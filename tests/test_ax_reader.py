"""Smoke tests for ax_reader helpers (no AX permissions required)."""
import sys
import unittest


class TestGetPidByNameContract(unittest.TestCase):
    """get_pid_by_name should return None for a non-existent app, not raise."""

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_missing_app_returns_none(self) -> None:
        from opp_server.ax_reader import get_pid_by_name

        result = get_pid_by_name("__nonexistent_app_xyz__")
        self.assertIsNone(result)

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_returns_int_for_running_app(self) -> None:
        from opp_server.ax_reader import get_pid_by_name

        # Finder is always running on macOS
        pid = get_pid_by_name("Finder")
        if pid is not None:
            self.assertIsInstance(pid, int)
            self.assertGreater(pid, 0)


if __name__ == "__main__":
    unittest.main()

