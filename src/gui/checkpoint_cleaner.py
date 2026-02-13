from datetime import datetime, timedelta
from pathlib import Path


async def cleanup_old_checkpoints(checkpoint_dir: Path, max_age_days: int = 7) -> int:
    """Delete checkpoints older than max_age_days. Returns count deleted."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0
    if checkpoint_dir.exists():
        for ckpt_file in checkpoint_dir.glob("*.json"):
            if ckpt_file.stat().st_mtime < cutoff.timestamp():
                ckpt_file.unlink()
                deleted += 1
    return deleted
