from typing import Callable
from typing import IO
from zipfile import ZipInfo

XhtmlProcessorFunc = Callable[[IO[bytes]], None]

FileProcessorFunc = Callable[[IO[bytes], ZipInfo], None]