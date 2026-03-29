# std
import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List

# lib
from dateutil import parser as dateutil_parser


@dataclass
class HarvesterActivityMessage:
    """Parsed information from harvester logs"""

    timestamp: datetime
    eligible_plots_count: int
    challenge_hash: str
    found_proofs_count: int
    search_time_seconds: float
    total_plots_count: int


class HarvesterActivityParser:
    """This class can parse info log messages from the chia harvester.

    Requires Chia 2.6.0 or later. You need to have enabled "log_level: INFO"
    in your chia config.yaml (usually under ~/.chia/mainnet/config/config.yaml).

    Expected log format (Chia 2.6.0+):
        TIMESTAMP VERSION harvester chia.harvester.harvester: INFO
        challenge_hash: HASH ...N plots were eligible for farming challengeFound
        N V1 proofs and N V2 qualities. Time: N s. Total N plots
    """

    def __init__(self):
        logging.debug("Enabled parser for harvester activity - eligible plot events.")
        self._regex = re.compile(
            r"([0-9:.T-]+) (?:[-0-9a-zA-Z.]+ )?harvester (?:src|chia).harvester.harvester(?:\s?): INFO\s*"
            r"challenge_hash: ([0-9a-f]+) \.\.\.([0-9]+) plots were eligible for farming \w+Found "
            r"([0-9]+) V1 proofs and ([0-9]+) V2 qualities\. Time: ([0-9.]*) s\. Total ([0-9]*) plots"
        )

    def parse(self, logs: str) -> List[HarvesterActivityMessage]:
        """Parses all harvester activity messages from a bunch of logs.

        :param logs: String of logs - can be multi-line
        :returns: A list of parsed messages - can be empty
        """

        parsed_messages = []
        for match in self._regex.findall(logs):
            parsed_messages.append(
                HarvesterActivityMessage(
                    timestamp=dateutil_parser.parse(match[0]),
                    eligible_plots_count=int(match[2]),
                    challenge_hash=match[1],
                    found_proofs_count=int(match[3]),  # V1 proofs (actual block proofs)
                    search_time_seconds=float(match[5]),
                    total_plots_count=int(match[6]),
                )
            )
        return parsed_messages
