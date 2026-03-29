# std
import unittest
from unittest.mock import patch, MagicMock

# project
from src.chia_log.handlers.blockchain_db_handler import BlockchainDbHandler
from src.notifier import EventType, EventPriority, EventService


class _Usage:
    def __init__(self, total, free):
        self.total = total
        self.used = total - free
        self.free = free


_USAGE_OK = _Usage(total=1_000_000_000_000, free=500_000_000_000)   # 50% free — well above 10%
_USAGE_LOW = _Usage(total=1_000_000_000_000, free=50_000_000_000)    # 5% free — below 10%

_DB_PATH = "/mnt/chia_db/blockchain_v2_mainnet.sqlite"


def _make_config(db_path=None, threshold=10.0):
    """Build a minimal confuse-compatible config stub."""
    cfg = MagicMock()
    cfg.__bool__ = lambda self: True

    def side_effect(key):
        child = MagicMock()
        if key == "db_path":
            child.get.return_value = db_path
        elif key == "low_disk_threshold_pct":
            child.get.return_value = threshold
        else:
            child.get.side_effect = Exception(f"unknown key {key}")
        return child

    cfg.__getitem__ = MagicMock(side_effect=side_effect)
    return cfg


class TestBlockchainDbHandlerNoop(unittest.TestCase):
    """When db_path is absent the handler must be a complete no-op."""

    def testNoEventsWhenDbPathNotConfigured(self):
        handler = BlockchainDbHandler(_make_config(db_path=None))
        events = handler.handle("some log line")
        self.assertEqual(events, [])

    def testNoEventsWithoutConfig(self):
        handler = BlockchainDbHandler(config=None)
        events = handler.handle("some log line")
        self.assertEqual(events, [])


class TestBlockchainDbHandlerStartup(unittest.TestCase):
    """Startup check: INFO log + correct event behaviour."""

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testNoStartupAlertWhenSpaceOk(self, _ismount, _usage):
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH))
        events = handler.handle("")
        self.assertEqual(events, [], "No alert expected when disk has plenty of space")

    @patch("shutil.disk_usage", return_value=_USAGE_LOW)
    @patch("os.path.ismount", return_value=True)
    def testStartupAlertWhenSpaceLow(self, _ismount, _usage):
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH, threshold=10.0))
        events = handler.handle("")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.USER)
        self.assertEqual(events[0].priority, EventPriority.HIGH)
        self.assertEqual(events[0].service, EventService.FULL_NODE)
        self.assertIn("Low disk space", events[0].message)

    @patch("shutil.disk_usage", return_value=_USAGE_LOW)
    @patch("os.path.ismount", return_value=True)
    def testStartupAlertDrainedOnFirstHandleOnly(self, _ismount, _usage):
        """The queued startup event must be returned exactly once."""
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH, threshold=10.0))
        first = handler.handle("")
        second = handler.handle("")
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testStartupInfoLogged(self, _ismount, _usage):
        """An INFO log about disk space must be emitted at startup."""
        with self.assertLogs("root", level="INFO") as log_ctx:
            BlockchainDbHandler(_make_config(db_path=_DB_PATH))
        logged = "\n".join(log_ctx.output)
        self.assertIn("disk space at startup", logged)
        self.assertIn("GB free", logged)


class TestBlockchainDbHandlerStatsManager(unittest.TestCase):
    """StatsManager integration: path forwarded, daily checker registered."""

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testForwardsDbPathToStatsManager(self, _ismount, _usage):
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH))
        stats_manager = MagicMock()
        handler.handle("", stats_manager)
        stats_manager.set_blockchain_db_path.assert_called_once_with(_DB_PATH)

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testRegistersDailyChecker(self, _ismount, _usage):
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH))
        stats_manager = MagicMock()
        handler.handle("", stats_manager)
        stats_manager.register_daily_checker.assert_called_once()

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testRegistersWithStatsManagerOnlyOnce(self, _ismount, _usage):
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH))
        stats_manager = MagicMock()
        handler.handle("", stats_manager)
        handler.handle("", stats_manager)
        stats_manager.set_blockchain_db_path.assert_called_once()
        stats_manager.register_daily_checker.assert_called_once()

    @patch("shutil.disk_usage", return_value=_USAGE_OK)
    @patch("os.path.ismount", return_value=True)
    def testDailyCheckerCallableFunctional(self, _ismount, _usage):
        """The registered callable must return [] when there is no alert."""
        handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH))
        stats_manager = MagicMock()
        handler.handle("", stats_manager)
        checker_fn = stats_manager.register_daily_checker.call_args[0][0]
        self.assertEqual(checker_fn(), [])

    @patch("os.path.ismount", return_value=True)
    def testDailyCheckerCallableReturnsEventWhenLow(self, _ismount):
        """The registered callable must return a HIGH event when disk is low."""
        with patch("shutil.disk_usage", return_value=_USAGE_OK):
            handler = BlockchainDbHandler(_make_config(db_path=_DB_PATH, threshold=10.0))
        stats_manager = MagicMock()
        with patch("shutil.disk_usage", return_value=_USAGE_OK):
            handler.handle("", stats_manager)
        checker_fn = stats_manager.register_daily_checker.call_args[0][0]
        with patch("shutil.disk_usage", return_value=_USAGE_LOW):
            events = checker_fn()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].priority, EventPriority.HIGH)


if __name__ == "__main__":
    unittest.main()
