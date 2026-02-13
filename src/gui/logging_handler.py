import logging
from collections import deque
from typing import Callable


class GUILogHandler(logging.Handler):
    """Captures logs for GUI display"""

    def __init__(self, callback: Callable[[str], None], max_records: int = 500):
        super().__init__()
        self.callback = callback
        self.records: deque[str] = deque(maxlen=max_records)
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.records.append(msg)
            self.callback(msg)
        except Exception:
            self.handleError(record)


def setup_gui_logging(callback: Callable[[str], None]) -> GUILogHandler:
    handler = GUILogHandler(callback)
    handler.setLevel(logging.INFO)
    logging.getLogger("src").addHandler(handler)
    return handler
