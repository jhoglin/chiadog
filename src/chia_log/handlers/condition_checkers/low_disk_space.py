# std
import logging
import shutil
from typing import Optional

# project
from src.chia_log.handlers.daily_stats.stat_accumulators.disk_space_stats import DiskSpaceStats
from src.notifier import Event, EventService, EventType, EventPriority


class LowDiskSpace:
    """Check whether free disk space on the blockchain DB filesystem is below a threshold.

    The db_path is provided at construction time from config — its presence is the
    feature flag.  check() can be called at any time; it returns an Event on the
    first threshold-crossing and resets when space recovers.
    """

    def __init__(self, db_path: str, threshold_pct: float):
        logging.debug(f"Enabled check for low disk space on '{db_path}' (threshold: {threshold_pct}%)")
        self._db_path = db_path
        self._threshold_pct = threshold_pct
        self._alerted = False

    def check(self) -> Optional[Event]:
        try:
            mount = DiskSpaceStats._get_mount_point(self._db_path)
            usage = shutil.disk_usage(mount)
            pct_free = (usage.free / usage.total) * 100
        except OSError as e:
            logging.warning(f"LowDiskSpace: could not read disk usage for '{self._db_path}': {e}")
            return None

        if pct_free < self._threshold_pct:
            if not self._alerted:
                free_gb = usage.free / (1024**3)
                total_gb = usage.total / (1024**3)
                message = (
                    f"Low disk space on blockchain DB filesystem ({mount})! "
                    f"Only {free_gb:.1f} GB free of {total_gb:.1f} GB "
                    f"({pct_free:.1f}% free, threshold: {self._threshold_pct:.0f}%)."
                )
                logging.warning(message)
                self._alerted = True
                return Event(
                    type=EventType.USER,
                    priority=EventPriority.HIGH,
                    service=EventService.FULL_NODE,
                    message=message,
                )
        else:
            # Reset so the alert fires again if disk fills up after recovery
            self._alerted = False

        return None
