# std
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

# project
from .. import BlockchainDbConsumer, BlockchainDbMessage, StatAccumulator


class DiskSpaceStats(BlockchainDbConsumer, StatAccumulator):
    """Report free disk space on the filesystem where the blockchain database lives.

    The DB path is extracted from the startup log line:
        "using blockchain database <path>, which is version 2"

    Once a path is known, get_summary() calls shutil.disk_usage() at report time
    so the value reflects the current state, not the state when the DB was first seen.
    """

    def __init__(self):
        self._last_reset_time = datetime.now()
        self._db_path: str = ""

    def reset(self):
        self._last_reset_time = datetime.now()
        # Keep the path — it doesn't change between summary cycles.

    def consume(self, obj: BlockchainDbMessage):
        if not self._db_path:
            self._db_path = obj.db_path
            logging.info(f"DiskSpaceStats: tracking disk usage for path '{self._db_path}'")

    def get_summary(self) -> str:
        if not self._db_path:
            return "DB disk 💾: Unknown (no database path seen yet)"

        try:
            mount = self._get_mount_point(self._db_path)
            usage = shutil.disk_usage(mount)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            pct_free = (usage.free / usage.total) * 100
            return f"DB disk 💾: {free_gb:.1f} GB free of {total_gb:.1f} GB ({pct_free:.1f}% free) on {mount}"
        except OSError as e:
            logging.warning(f"DiskSpaceStats: could not read disk usage for '{self._db_path}': {e}")
            return f"DB disk 💾: Unable to read ({e})"

    def get_free_percent(self) -> float:
        """Return the current free-space percentage, or 100.0 if the path is unknown."""
        if not self._db_path:
            return 100.0
        try:
            mount = self._get_mount_point(self._db_path)
            usage = shutil.disk_usage(mount)
            return (usage.free / usage.total) * 100
        except OSError:
            return 100.0

    @property
    def db_path(self) -> str:
        return self._db_path

    @staticmethod
    def _get_mount_point(path: str) -> str:
        """Walk up to find the nearest mount point for a given path."""
        p = Path(path)
        # Use the directory if the path is a file that may not exist yet
        candidate = p if p.is_dir() else p.parent
        while not os.path.ismount(str(candidate)):
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
        return str(candidate)
