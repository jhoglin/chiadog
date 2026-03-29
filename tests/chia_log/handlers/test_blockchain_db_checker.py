# std
import unittest
from unittest.mock import patch

# project
from src.chia_log.handlers.condition_checkers.low_disk_space import LowDiskSpace
from src.notifier import EventType, EventPriority, EventService


class _Usage:
    def __init__(self, total, free):
        self.total = total
        self.used = total - free
        self.free = free


_DB_PATH = "/mnt/chia_db/blockchain_v2_mainnet.sqlite"
_THRESHOLD = 10.0

_USAGE_OK = _Usage(total=1_000_000_000_000, free=500_000_000_000)   # 50% free
_USAGE_LOW = _Usage(total=1_000_000_000_000, free=50_000_000_000)    # 5% free
_USAGE_EXACT = _Usage(total=1_000_000_000_000, free=100_000_000_000) # exactly 10% free


class TestLowDiskSpace(unittest.TestCase):
    def _make_checker(self, threshold=_THRESHOLD):
        return LowDiskSpace(db_path=_DB_PATH, threshold_pct=threshold)

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testNoAlertWhenSpaceIsPlentiful(self, _ismount, _usage):
        checker = self._make_checker()
        event = checker.check()
        self.assertIsNone(event)

    @patch("shutil.disk_usage", return_value=_USAGE_LOW)
    @patch("os.path.ismount", return_value=True)
    def testAlertWhenBelowThreshold(self, _ismount, _usage):
        checker = self._make_checker()
        event = checker.check()
        self.assertIsNotNone(event)
        self.assertEqual(event.type, EventType.USER)
        self.assertEqual(event.priority, EventPriority.HIGH)
        self.assertEqual(event.service, EventService.FULL_NODE)
        self.assertIn("Low disk space", event.message)
        self.assertIn("5.0%", event.message)
        self.assertIn(f"threshold: {int(_THRESHOLD)}%", event.message)

    @patch("shutil.disk_usage", return_value=_USAGE_LOW)
    @patch("os.path.ismount", return_value=True)
    def testAlertFiresOnlyOnce(self, _ismount, _usage):
        """Second check while still below threshold must not re-fire."""
        checker = self._make_checker()
        event1 = checker.check()
        event2 = checker.check()
        self.assertIsNotNone(event1)
        self.assertIsNone(event2)

    @patch("os.path.ismount", return_value=True)
    def testAlertResetsAfterRecovery(self, _ismount):
        """After recovering above threshold the alert must fire again on the next drop."""
        checker = self._make_checker()
        with patch("shutil.disk_usage", return_value=_USAGE_LOW):
            event1 = checker.check()
        self.assertIsNotNone(event1)

        # Space recovers
        with patch("shutil.disk_usage", return_value=_USAGE_OK):
            event2 = checker.check()
        self.assertIsNone(event2)

        # Drops again — must alert again
        with patch("shutil.disk_usage", return_value=_USAGE_LOW):
            event3 = checker.check()
        self.assertIsNotNone(event3)

    @patch("shutil.disk_usage", return_value=_USAGE_EXACT)
    @patch("os.path.ismount", return_value=True)
    def testNoAlertAtExactThreshold(self, _ismount, _usage):
        """Free space exactly equal to the threshold is not below it."""
        checker = self._make_checker()
        event = checker.check()
        self.assertIsNone(event)

    @patch("shutil.disk_usage", side_effect=OSError("device gone"))
    @patch("os.path.ismount", return_value=True)
    def testNoAlertOnOSError(self, _ismount, _usage):
        checker = self._make_checker()
        event = checker.check()
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
