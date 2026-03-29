# std
import logging
from typing import List, Optional

# project
from . import LogHandlerInterface
from ..parsers.blockchain_db_parser import BlockchainDbParser
from .condition_checkers import BlockchainDbConditionChecker
from .condition_checkers.low_disk_space import LowDiskSpace
from .daily_stats.stats_manager import StatsManager
from .daily_stats.stat_accumulators.disk_space_stats import DiskSpaceStats
from src.notifier import Event


class BlockchainDbHandler(LogHandlerInterface):
    """Handle log lines that report the blockchain database path.

    Responsibilities:
    - Feed the DB path to the DiskSpaceStats accumulator (for daily summary)
    - Check disk space against the configured threshold and fire an alert if low
    """

    _DEFAULT_LOW_DISK_THRESHOLD_PCT = 10.0

    @staticmethod
    def config_name() -> str:
        return "blockchain_db_handler"

    def __init__(self, config=None):
        super().__init__(config)
        self._parser = BlockchainDbParser()

        try:
            threshold_pct = float(config["low_disk_threshold_pct"].get()) if config else self._DEFAULT_LOW_DISK_THRESHOLD_PCT
        except Exception:
            threshold_pct = self._DEFAULT_LOW_DISK_THRESHOLD_PCT

        self._cond_checkers: List[BlockchainDbConditionChecker] = [
            LowDiskSpace(threshold_pct=threshold_pct),
        ]

    def handle(self, logs: str, stats_manager: Optional[StatsManager] = None) -> List[Event]:
        events = []
        messages = self._parser.parse(logs)

        for msg in messages:
            # Update the disk space stat accumulator in StatsManager if present
            if stats_manager is not None:
                stats_manager.consume_blockchain_db_messages([msg])

            for checker in self._cond_checkers:
                event = checker.check(msg)
                if event:
                    events.append(event)

        return events
