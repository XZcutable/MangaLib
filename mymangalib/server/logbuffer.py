"""The server's recent warnings and errors, kept in memory so a bug report can include them.
Records still go to the console as before; this only keeps a copy of the last few hundred."""
import collections, logging, re, threading, time
from typing import Optional

MAX_RECORDS = 300
LOGGER_NAME = "mymangalib"

# Values that would let someone use an account, if a message happens to contain them
_SECRETS = re.compile(r"(Bearer\s+|[?&](?:t|token|code)=)[^\s&\"']+", re.IGNORECASE)

def redact(text: str) -> str:
    return _SECRETS.sub(r"\1[hidden]", text)

class BufferHandler(logging.Handler):
    def __init__(self, capacity: int = MAX_RECORDS):
        super().__init__(level=logging.WARNING)
        self.records: "collections.deque[tuple[float, str]]" = collections.deque(maxlen=capacity)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        self._records_lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        try:
            text = redact(self.format(record))
        except Exception:
            return
        with self._records_lock:
            self.records.append((record.created, text))

    def since(self, seconds: float) -> list[str]:
        cutoff = time.time() - seconds
        with self._records_lock:
            return [text for created, text in self.records if created >= cutoff]

_handler: Optional[BufferHandler] = None

def install() -> BufferHandler:
    """Adds the buffer to the "mymangalib" logger once per process, plus a console handler so the
    messages still show in the terminal and `docker compose logs`."""
    global _handler
    logger = logging.getLogger(LOGGER_NAME)
    if _handler is None:
        _handler = BufferHandler()
        logger.addHandler(_handler)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(console)
        logger.setLevel(logging.INFO)
    return _handler

def logger(name: str = "") -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)

def recent(seconds: float = 30 * 60) -> str:
    return "\n".join(_handler.since(seconds)) if _handler else ""
