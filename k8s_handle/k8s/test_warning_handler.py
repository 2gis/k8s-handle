import unittest

from .warning_handler import WarningHandler


class TestWarningHandler(unittest.TestCase):
    def setUp(self):
        self.handler = WarningHandler()

    def test_handle_warning_header(self):
        with self.assertLogs("k8s_handle.k8s.warning_handler", level="WARNING") as cm:
            self.handler.handle_warning_header(299, "-", "warning")

        self.assertEqual(cm.output, ['WARNING:k8s_handle.k8s.warning_handler:\x1b[33;1m\n'
                                     '        ▄▄\n'
                                     '       ████\n'
                                     '      ██▀▀██\n'
                                     '     ███  ███     warning\n'
                                     '    ████▄▄████\n'
                                     '   █████  █████\n'
                                     '  ██████████████\n'
                                     '\x1b[0m'])

    def test_handle_warning_header_with_unexpected_code(self):
        with self.assertNoLogs("k8s_handle.k8s.warning_handler", level="WARNING"):
            self.handler.handle_warning_header(0, "-", "warning")

    def test_handle_warning_header_with_empty_message(self):
        with self.assertNoLogs("k8s_handle.k8s.warning_handler", level="WARNING"):
            self.handler.handle_warning_header(299, "-", "")

    def test_handle_warning_header_with_duplicate_messages(self):
        with self.assertLogs("k8s_handle.k8s.warning_handler", level="WARNING"):
            self.handler.handle_warning_header(299, "-", "warning")

        with self.assertNoLogs("k8s_handle.k8s.warning_handler", level="WARNING"):
            self.handler.handle_warning_header(299, "-", "warning")
