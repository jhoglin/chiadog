# std
import logging
import shutil
from typing import List, Optional

# project
from . import LogHandlerInterface
from .condition_checkers.low_disk_space import LowDiskSpace
from .daily_stats.stats_manager import StatsManager
from .daily_stats.stat_accumulators.disk_space_stats import DiskSpaceStats
from src.notifier import Event


class BlockchainDbHandler(LogHandlerInterface):
    """Monitor free disk space on the blockchain database filesystem.

    The presence of 'db_path' in config acts as the feature flag:
    - If set: disk space is checked at startup, an INFO log is written, a high-priority
      alert is queued if space is below the threshold, and the path is forwarded to
      StatsManager so it appears in the daily summary.
    - If absent: this handler is a no-op.

    No log-line parsing is performed — the DB path comes exclusively from config.
    """

    _DEFAULT_LOW_DISK_THRESHOLD_PCT = 10.0

    @staticmethod
    def config_name() -> str:
        return "blockchain_db_handler"

    def __init__(self, config=None):
        super().__init__(config)
        self._pending_events: List[Event] = []
        self._checker: Optional[LowDiskSpace] = None
        self._db_path_forwarded = False

        try:
            self._db_path = config["db_path"].get() if config else None
        except Exception:
            self._db_path = None

        try:
            threshold_pct = (
                float(config["low_disk_threshold_pct"].get()) if config else self._DEFAULT_LOW_DISK_THRESHOLD_PCT
            )
        except Exception:
            threshold_pct = self._DEFAULT_LOW_DISK_THRESHOLD_PCT

        if self._db_path:
            self._checker = LowDiskSpace(db_path=self._db_path, threshold_pct=threshold_pct)
            self._run_startup_check()
        else:
            self._checker = None
            logging.info("BlockchainDbHandler: db_path not configured — disk space monitoring disabled")

    def _run_startup_check(self) -> None:
        """Log INFO about current disk space and queue a warning event if space is low."""
        assert self._db_path is not None
        try:
            mount = DiskSpaceStats._get_mount_point(self._db_path)
            usage = shutil.disk_usage(mount)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            pct_free = (usage.free / usage.total) * 100
            logging.info(
                f"Blockchain DB disk space at startup: "
                f"{free_gb:.1f} GB free of {total_gb:.1f} GB "
                f"({pct_free:.1f}% free) on {mount}"
            )
        except OSError as e:
            logging.warning(f"BlockchainDbHandler: could not read disk usage for '{self._db_path}': {e}")
            return

        assert self._checker is not None
        event = self._checker.check()
        if event:
            self._pending_events.append(event)

    def handle(self, logs: str, stats_manager: Optional[StatsManager] = None) -> List[Event]:
        if not self._db_path:
            return []

        # Drain startup events on the first call
        events = self._pending_events
        self._pending_events = []

        # Register with StatsManager once: daily summary line + periodic low-disk check
        if not self._db_path_forwarded and stats_manager is not None:
            stats_manager.set_blockchain_db_path(self._db_path)
            checker = self._checker
            if checker is not None:
                stats_manager.register_daily_checker(lambda: [e for e in [checker.check()] if e])
            self._db_path_forwarded = True

        return events
