"""
Persistence module for checkpoint management.

Provides storage backends and high-level checkpoint management
for resumable translation jobs.
"""

from .base import PersistenceBackend, PersistenceError
from .file_backend import FilePersistenceBackend
from .manager import CheckpointManager
from .models import JobStage, JobStatus, StageProgress, STAGE_WEIGHTS

__all__ = [
    # Base
    "PersistenceBackend",
    "PersistenceError",
    # Backends
    "FilePersistenceBackend",
    # Manager
    "CheckpointManager",
    # Models
    "JobStage",
    "JobStatus",
    "StageProgress",
    "STAGE_WEIGHTS",
]
