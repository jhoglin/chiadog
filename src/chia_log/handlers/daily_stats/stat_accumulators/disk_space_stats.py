# std
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

# project
from .. import StatAccumulator


class DiskSpaceStats(StatAccumulator):
    """Report free disk space on the filesystem where the blockchain database lives.

    The DB path is supplied via set_db_path(), called by BlockchainDbHandler on its
    first handle() invocation once it reads db_path from config.

    get_summary() calls shutil.disk_usage() at report time so the value always
    reflects the current state of the disk.
    """

    def __init__(self):
        self._last_reset_time = datetime.now()
        self._db_path: str = ""

    def set_db_path(self, db_path: str) -> None:
        if not self._db_path:
            self._db_path = db_path
            logging.info(f"DiskSpaceStats: tracking disk usage for path '{db_path}'")

    def reset(self):
        self._last_reset_time = datetime.now()
        # Keep the path — it doesn't change between summary cycles.

    def get_summary(self) -> str:
        if not self._db_path:
            return "DB disk 💾: Unknown (db_path not configured)"

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

    @staticmethod
    def _get_mount_point(path: str) -> str:
        """Walk up the directory tree to find the nearest mount point."""
        p = Path(path)
        candidate = p if p.is_dir() else p.parent
        while not os.path.ismount(str(candidate)):
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
        return str(candidate)
