import types
import unittest
from unittest.mock import Mock
from unittest.mock import call
from unittest.mock import patch

from urllib3 import HTTPResponse
from kubernetes.client.rest import RESTResponse

from k8s_handle.exceptions import InvalidWarningHeader
from .api_clients import ApiClientWithWarningHandler


class TestApiClientWithWarningHandler(unittest.TestCase):
    def setUp(self):
        self.warning_handler = types.SimpleNamespace()
        self.warning_handler.handle_warning_header = Mock()
        self.api_client = ApiClientWithWarningHandler(warning_handler=self.warning_handler)

    @patch('kubernetes.client.api_client.ApiClient.request')
    def _test_request(self, headers, mocked_request):
        mocked_request.return_value = RESTResponse(HTTPResponse(headers=headers))
        self.api_client.request()
        return self.api_client.warning_handler.handle_warning_header

    def test_request(self):
        handler = self._test_request([
            ('Warning', '299 - "warning 1"'),
        ])
        handler.assert_called_with(299, '-', 'warning 1')

    def test_request_with_multiple_headers(self):
        handler = self._test_request([
            ('Warning', '299 - "warning 1"'),
            ('Warning', '299 - "warning 2", 299 - "warning 3"'),
        ])
        handler.assert_has_calls([
            call(299, '-', 'warning 1'),
            call(299, '-', 'warning 2'),
            call(299, '-', 'warning 3'),
        ])

    def test_request_without_header(self):
        headers = []
        self._test_request(headers).assert_not_called()

    def test_request_with_invalid_headers(self):
        with self.assertLogs("k8s_handle.k8s.api_clients", level="ERROR"):
            self._test_request([
                ('Warning', 'invalid'),
            ])

    def test_parse_warning_headers(self):
        self.assertEqual(
            self.api_client._parse_warning_headers(
                ['299 - "warning 1"'],
            ),
            [(299, '-', 'warning 1')],
        )

    def test_parse_warning_headers_with_invalid_header(self):
        with self.assertRaisesRegex(InvalidWarningHeader, "Invalid warning header: fewer than 3 segments"):
            self.api_client._parse_warning_headers(['invalid'])

    def test_parse_warning_headers_with_invalid_code(self):
        with self.assertRaisesRegex(InvalidWarningHeader, "Invalid warning header: code segment is not 3 digits"):
            self.api_client._parse_warning_headers(['1000 - "warning 3"'])

    def test_parse_warning_headers_with_unquoted_text(self):
        with self.assertRaisesRegex(
            InvalidWarningHeader,
            "Invalid warning header: invalid quoted string: missing closing quote"
        ):
            self.api_client._parse_warning_headers(['299 - "warning unquoted'])
