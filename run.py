#!/usr/bin/env python3
"""
Simple script to run the EPUB translation pipeline.

Usage:
    python run.py [epub_path]
    python run.py demo_files/sample.epub
    python run.py book.epub --target ko
    python run.py book.epub --target ja --source en

Environment:
    OPENAI_API_KEY: Required. Your OpenAI API key.
"""

import asyncio
import logging
import sys
from pathlib import Path

from src.pipeline import Language, PipelineConfig, PipelineOrchestrator
from src.pipeline.logging import setup_logging


# Configure logging (pipeline-wide)
setup_logging(level="INFO")
logger = logging.getLogger(__name__)


# Language mapping
LANGUAGE_MAP = {
    "ko": Language.KOREAN,
    "en": Language.ENGLISH,
    "ja": Language.JAPANESE,
    "zh-cn": Language.CHINESE_SIMPLIFIED,
    "zh-tw": Language.CHINESE_TRADITIONAL,
}


def parse_args():
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Translate an EPUB file to another language.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py demo_files/sample.epub
    python run.py book.epub --target ja
    python run.py book.epub --source en --target ko
        """,
    )
    parser.add_argument(
        "epub_path",
        nargs="?",
        default="demo_files/sample.epub",
        help="Path to the EPUB file (default: demo_files/sample.epub)",
    )
    parser.add_argument(
        "--source", "-s",
        default=None,
        choices=list(LANGUAGE_MAP.keys()),
        help="Source language (default: from .env)",
    )
    parser.add_argument(
        "--target", "-t",
        default=None,
        choices=list(LANGUAGE_MAP.keys()),
        help="Target language (default: from .env)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory (default: from .env)",
    )
    parser.add_argument(
        "--checkpoint-dir", "-c",
        default=None,
        help="Checkpoint directory (default: from .env)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="OpenAI model to use (default: from .env)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing checkpoints before running",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args()


async def main():
    """Run the translation pipeline."""
    args = parse_args()

    # Set debug logging if requested
    if args.debug:
        setup_logging(level="DEBUG")
        logging.getLogger("httpx").setLevel(logging.INFO)

    # Validate EPUB path
    epub_path = Path(args.epub_path)
    if not epub_path.exists():
        logger.error("EPUB file not found: %s", epub_path)
        sys.exit(1)

    # Build CLI overrides (only explicitly provided args)
    cli_overrides = {}
    if args.source:
        cli_overrides["source_language"] = LANGUAGE_MAP[args.source]
    if args.target:
        cli_overrides["target_language"] = LANGUAGE_MAP[args.target]
    if args.model:
        cli_overrides["model"] = args.model
    if args.output_dir:
        cli_overrides["output_dir"] = Path(args.output_dir)
    if args.checkpoint_dir:
        cli_overrides["checkpoint_dir"] = Path(args.checkpoint_dir)

    # Create config from .env + CLI overrides
    config = PipelineConfig.from_env(**cli_overrides)

    # Check for API key (.env is already loaded by from_env)
    import os
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable is not set")
        logger.info("Set it in .env or with: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("EPUB Translation Pipeline")
    logger.info("=" * 60)
    logger.info("Input:  %s", epub_path)
    logger.info("Source: %s", config.source_language.value)
    logger.info("Target: %s", config.target_language.value)
    logger.info("Model:  %s", config.model)
    logger.info("Output: %s", config.output_dir)
    logger.info("=" * 60)

    # Create and initialize orchestrator
    orchestrator = PipelineOrchestrator(config)
    await orchestrator.initialize()

    # Clear checkpoints if requested
    if args.clear:
        logger.info("Clearing existing checkpoints...")
        count = await orchestrator.clear_job(epub_path)
        logger.info("Cleared %d checkpoint keys", count)

    # Check for existing job
    status = await orchestrator.get_job_status(epub_path)
    if status:
        logger.info("Resuming from: %s (%.1f%% complete)", status.stage.value, status.overall_percentage)

    # Run the pipeline
    try:
        logger.info("Starting translation...")
        result = await orchestrator.run(epub_path)

        logger.info("=" * 60)
        if result.success:
            logger.info("✓ Translation completed successfully!")
        else:
            logger.warning("⚠ Translation completed with %d errors", len(result.errors))
            for error in result.errors[:5]:  # Show first 5 errors
                logger.warning("  - %s", error)
            if len(result.errors) > 5:
                logger.warning("  ... and %d more errors", len(result.errors) - 5)

        logger.info("Output: %s", result.output_path)
        logger.info("=" * 60)

        return 0 if result.success else 1

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
