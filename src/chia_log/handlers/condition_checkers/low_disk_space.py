# std
import logging
import shutil
from typing import Optional
from pathlib import Path
import os

# project
from . import BlockchainDbConditionChecker
from src.chia_log.parsers.blockchain_db_parser import BlockchainDbMessage
from src.chia_log.handlers.daily_stats.stat_accumulators.disk_space_stats import DiskSpaceStats
from src.notifier import Event, EventService, EventType, EventPriority


class LowDiskSpace(BlockchainDbConditionChecker):
    """Alert when free disk space on the blockchain DB filesystem drops below a threshold.

    The threshold is configurable (default: 10%).  The alert fires at most once per
    threshold-crossing to avoid flooding the user with repeated notifications.
    """

    _DEFAULT_THRESHOLD_PCT = 10.0

    def __init__(self, threshold_pct: float = _DEFAULT_THRESHOLD_PCT, disk_space_stats: Optional[DiskSpaceStats] = None):
        logging.debug(f"Enabled check for low disk space (threshold: {threshold_pct}%)")
        self._threshold_pct = threshold_pct
        self._disk_space_stats = disk_space_stats
        self._alerted = False

    def check(self, obj: BlockchainDbMessage) -> Optional[Event]:
        # Update the shared stats accumulator if provided
        if self._disk_space_stats is not None:
            self._disk_space_stats.consume(obj)

        db_path = obj.db_path
        try:
            mount = DiskSpaceStats._get_mount_point(db_path)
            usage = shutil.disk_usage(mount)
            pct_free = (usage.free / usage.total) * 100
        except OSError as e:
            logging.warning(f"LowDiskSpace: could not read disk usage for '{db_path}': {e}")
            return None

        if pct_free < self._threshold_pct:
            if not self._alerted:
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
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
