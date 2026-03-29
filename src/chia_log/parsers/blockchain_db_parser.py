# std
import re
import logging
from dataclasses import dataclass
from typing import List


@dataclass
class BlockchainDbMessage:
    """Parsed information from the blockchain database startup log line"""

    db_path: str


class BlockchainDbParser:
    """Parse the log line emitted at startup that reveals the blockchain database path.

    Example log line (Chia 2.6.0):
        2026-03-23T22:43:26.808 2.6.0 full_node chia.full_node.full_node: INFO
            using blockchain database /mnt/disk02-10/chia_db/blockchain_v2_mainnet.sqlite, which is version 2
    """

    def __init__(self):
        logging.debug("Enabled parser for blockchain database path.")
        self._regex = re.compile(
            r"(?:[-0-9a-zA-Z.]+ )?full_node (?:src|chia)\.full_node\.full_node(?:\s*)?: INFO\s+"
            r"using blockchain database (\S+),\s+which is version"
        )

    def parse(self, logs: str) -> List[BlockchainDbMessage]:
        """Parse all blockchain database path messages from a log string.

        :param logs: String of logs - can be multi-line
        :returns: A list of parsed messages - typically at most one per node restart
        """
        parsed_messages = []
        for match in self._regex.findall(logs):
            parsed_messages.append(BlockchainDbMessage(db_path=match))
        return parsed_messages
