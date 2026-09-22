import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from core import logger as logger_module
from services.logging_hardening import log_event, logging_status, redact_mapping


class Phase59LoggingTests(unittest.TestCase):
    def test_redacts_common_secret_fields(self):
        result = redact_mapping({"password": "secret", "token": "abc", "user": "cashier"})
        self.assertEqual(result["password"], "***REDACTED***")
        self.assertEqual(result["token"], "***REDACTED***")
        self.assertEqual(result["user"], "cashier")

    def test_logging_status_has_expected_shape(self):
        status = logging_status()
        self.assertIn("file_logging", status)
        self.assertIn("writable", status)
        self.assertIn("path", status)

    def test_log_event_redacts_context(self):
        handler = logging.StreamHandler()
        logger_module.logger.addHandler(handler)
        with patch.object(logger_module.logger, "log") as mocked:
            log_event("test event", password="dont-log-this", user="cashier")
        logger_module.logger.removeHandler(handler)
        _level, fmt, text, suffix = mocked.call_args.args
        rendered = fmt % (text, suffix)
        self.assertIn("***REDACTED***", rendered)
        self.assertNotIn("dont-log-this", rendered)

    def test_log_path_is_path_like(self):
        self.assertIsInstance(Path(logger_module.LOG_PATH), Path)


if __name__ == "__main__":
    unittest.main()
