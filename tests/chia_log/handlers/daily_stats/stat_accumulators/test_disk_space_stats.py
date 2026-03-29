# std
import unittest
from unittest.mock import patch

# project
from src.chia_log.handlers.daily_stats.stat_accumulators.disk_space_stats import DiskSpaceStats


# A shutil.disk_usage namedtuple-compatible stand-in
class _Usage:
    def __init__(self, total, used, free):
        self.total = total
        self.used = used
        self.free = free


_USAGE_PLENTY = _Usage(total=1_000_000_000_000, used=500_000_000_000, free=500_000_000_000)  # 50% free
_USAGE_LOW = _Usage(total=1_000_000_000_000, used=950_000_000_000, free=50_000_000_000)  # 5% free


class TestDiskSpaceStats(unittest.TestCase):
    def setUp(self):
        self.stats = DiskSpaceStats()

    def testUnknownBeforePathSet(self):
        summary = self.stats.get_summary()
        self.assertIn("Unknown", summary)
        self.assertIn("db_path not configured", summary)

    @patch("shutil.disk_usage", return_value=_USAGE_PLENTY)
    @patch("os.path.ismount", return_value=True)
    def testSummaryAfterPathSet(self, _mock_ismount, _mock_usage):
        self.stats.set_db_path("/mnt/chia_db/blockchain_v2_mainnet.sqlite")
        summary = self.stats.get_summary()
        self.assertIn("GB free of", summary)
        self.assertIn("50.0% free", summary)
        self.assertIn("DB disk 💾", summary)

    @patch("shutil.disk_usage", return_value=_USAGE_PLENTY)
    @patch("os.path.ismount", return_value=True)
    def testSetDbPathIdempotent(self, _mock_ismount, _mock_usage):
        """Second call to set_db_path should be silently ignored."""
        self.stats.set_db_path("/first/path")
        self.stats.set_db_path("/second/path")
        self.stats.get_summary()  # should not raise
        self.assertEqual(self.stats._db_path, "/first/path")

    @patch("shutil.disk_usage", return_value=_USAGE_PLENTY)
    @patch("os.path.ismount", return_value=True)
    def testResetKeepsPath(self, _mock_ismount, _mock_usage):
        """reset() must preserve the path so subsequent summaries still work."""
        self.stats.set_db_path("/mnt/chia_db/blockchain_v2_mainnet.sqlite")
        self.stats.reset()
        summary = self.stats.get_summary()
        self.assertIn("GB free of", summary)

    @patch("shutil.disk_usage", side_effect=OSError("device not found"))
    @patch("os.path.ismount", return_value=True)
    def testSummaryOnOSError(self, _mock_ismount, _mock_usage):
        self.stats.set_db_path("/mnt/chia_db/blockchain_v2_mainnet.sqlite")
        summary = self.stats.get_summary()
        self.assertIn("Unable to read", summary)


if __name__ == "__main__":
    unittest.main()
