"""Structured logging via loguru. run_id per pytest run."""
from __future__ import annotations

import sys
import uuid

from loguru import logger

RUN_ID = uuid.uuid4().hex[:8]

logger.remove()
logger.add(sys.stderr, level="INFO",
           format="{time} | {level} | run={extra[run_id]} | {message}")
logger = logger.bind(run_id=RUN_ID)
