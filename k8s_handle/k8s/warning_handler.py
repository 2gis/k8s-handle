import logging

log = logging.getLogger(__name__)

YELLOW_COLOR = "\u001b[33;1m"
RESET_COLOR = "\u001b[0m"

WARNING_TEMPLATE = """
        ▄▄
       ████
      ██▀▀██
     ███  ███     {text}
    ████▄▄████
   █████  █████
  ██████████████
"""


class WarningHandler():
    def __init__(self):
        self.written = []

    def handle_warning_header(self, code, agent, text):
        if code != 299 or len(text) == 0:
            return

        if text in self.written:
            return

        log.warning(self._yellow(WARNING_TEMPLATE.format(text=text)))

        self.written += [text]

    @staticmethod
    def _yellow(str):
        return f"{YELLOW_COLOR}{str}{RESET_COLOR}"
