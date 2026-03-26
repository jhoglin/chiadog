# std
import unittest
from pathlib import Path

# project
from src.chia_log.parsers import finished_signage_point_parser


class TestFinishedSignagePointParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = finished_signage_point_parser.FinishedSignagePointParser()
        self.example_logs_path = Path(__file__).resolve().parents[1] / "logs/finished_signage_point"
        with open(self.example_logs_path / "nominal.txt", encoding="UTF-8") as f:
            self.nominal_logs = f.read()
        with open(self.example_logs_path / "nominal_old_log_format.txt", encoding="UTF-8") as f:
            self.nominal_logs_old_format = f.read()

    def tearDown(self) -> None:
        pass

    def testBasicParsing(self):
        for logs in [self.nominal_logs, self.nominal_logs_old_format]:
            # Check that important fields are correctly parsed
            signage_point_messages = self.parser.parse(logs)
            self.assertNotEqual(len(signage_point_messages), 0, "No log messages found")

            # Validate the sequence is internally consistent: each SP is +1 from
            # the previous, with a wrap-around from 64 back to 1.
            for i in range(1, len(signage_point_messages)):
                prev = signage_point_messages[i - 1].signage_point
                curr = signage_point_messages[i].signage_point
                expected_next = (prev % 64) + 1
                self.assertEqual(
                    curr,
                    expected_next,
                    f"SP sequence broken at index {i}: {prev} -> {curr} (expected {expected_next})",
                )


if __name__ == "__main__":
    unittest.main()
