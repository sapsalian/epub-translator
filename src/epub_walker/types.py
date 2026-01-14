from typing import Callable
from typing import IO

XhtmlProcessorFunc = Callable[[IO[bytes]], None]