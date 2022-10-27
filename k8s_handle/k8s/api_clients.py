import re
import logging

from kubernetes.client.api_client import ApiClient

from k8s_handle.exceptions import InvalidWarningHeader

log = logging.getLogger(__name__)


class ApiClientWithWarningHandler(ApiClient):
    def __init__(self, *args, **kwargs):
        self.warning_handler = kwargs.pop("warning_handler", None)

        ApiClient.__init__(self, *args, **kwargs)

    def request(self, *args, **kwargs):
        response_data = ApiClient.request(self, *args, **kwargs)

        if self.warning_handler is not None:
            headers = response_data.getheaders()

            if "Warning" in headers:
                self._handle_warnings([headers["Warning"]], self.warning_handler)

        return response_data

    @staticmethod
    def _handle_warnings(headers, handler):
        try:
            warnings = ApiClientWithWarningHandler._parse_warning_headers(headers)
        except InvalidWarningHeader as e:
            log.debug("Warning headers: {}".format(headers))
            log.error(e)
            return

        for warning in warnings:
            handler.handle_warning_header(*warning)

    @staticmethod
    def _parse_warning_headers(headers):
        """
        Based on `ParseWarningHeaders()` from k8s.io/apimachinery/pkg/util/net package.
        """
        results = []

        for header in headers:
            while len(header) > 0:
                result, remainder = ApiClientWithWarningHandler._parse_warning_header(header)
                results += [result]
                header = remainder

        return results

    @staticmethod
    def _parse_warning_header(header):
        """
        Based on `ParseWarningHeader()` from k8s.io/apimachinery/pkg/util/net package,
        but with much more permissive validation rules.
        """

        parts = header.split(" ", maxsplit=2)
        if len(parts) != 3:
            raise InvalidWarningHeader("Invalid warning header: fewer than 3 segments")

        (code, agent, textDateRemainder) = (parts[0], parts[1], parts[2])

        # verify code format
        codeMatcher = re.compile("^[0-9]{3}$")
        if not codeMatcher.match(code):
            raise InvalidWarningHeader("Invalid warning header: code segment is not 3 digits")

        code = int(code)

        # verify agent presence
        if len(agent) == 0:
            raise InvalidWarningHeader("Invalid warning header: empty agent segment")

        # verify textDateRemainder presence
        if len(textDateRemainder) == 0:
            raise InvalidWarningHeader("Invalid warning header: empty text segment")

        # extract text
        text, dateAndRemainder = ApiClientWithWarningHandler._parse_quoted_string(textDateRemainder)

        result = (code, agent, text)
        remainder = ""

        if len(dateAndRemainder) > 0:
            if dateAndRemainder[0] == '"':
                # consume date
                foundEndQuote = False
                for i in range(1, len(dateAndRemainder)):
                    if dateAndRemainder[i] == '"':
                        foundEndQuote = True
                        remainder = dateAndRemainder[i+1:].strip()
                        break

                if not foundEndQuote:
                    raise InvalidWarningHeader("Invalid warning header: unterminated date segment")
            else:
                remainder = dateAndRemainder

        if len(remainder) > 0:
            if remainder[0] == ',':
                # consume comma if present
                remainder = remainder[1:].strip()
            else:
                raise InvalidWarningHeader("Invalid warning header: unexpected token after warn-date")

        return result, remainder

    @staticmethod
    def _parse_quoted_string(quotedString):
        """
        Based on `parseQuotedString()` from k8s.io/apimachinery/pkg/util/net package.
        """

        if len(quotedString) == 0:
            raise InvalidWarningHeader("Invalid warning header: invalid quoted string: 0-length")

        if quotedString[0] != '"':
            raise InvalidWarningHeader("Invalid warning header: invalid quoted string: missing initial quote")

        quotedString = quotedString[1:]
        remainder = ""
        escaping = False
        closedQuote = False
        result = ""

        for i in range(0, len(quotedString)):
            b = quotedString[i]
            if b == '"':
                if escaping:
                    result += b
                    escaping = False
                else:
                    closedQuote = True
                    remainder = quotedString[i+1:].strip()
                    break
            elif b == '\\':
                if escaping:
                    result += b
                    escaping = False
                else:
                    escaping = True
            else:
                result += b
                escaping = False

        if not closedQuote:
            raise InvalidWarningHeader("Invalid warning header: invalid quoted string: missing closing quote")

        return (result, remainder)
