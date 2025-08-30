# app/core/infra/logging.py

import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from app.core.infra.config import settings


def configure_logging():
    """애플리케이션 로깅을 설정합니다(콘솔 + 파일 회전)."""
    root = logging.getLogger()
    level_name = (settings.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        ch.setLevel(level)
        root.addHandler(ch)

    try:
        log_dir = settings.LOG_DIR or "logs"
        os.makedirs(log_dir, exist_ok=True)
        logfile = os.path.join(log_dir, f"{settings.LOG_FILE_BASENAME}.log")
        if not any(isinstance(h, TimedRotatingFileHandler) for h in root.handlers):
            fh = TimedRotatingFileHandler(
                filename=logfile,
                when=settings.LOG_ROTATE_WHEN,
                interval=int(settings.LOG_ROTATE_INTERVAL or 1),
                backupCount=int(settings.LOG_BACKUP_COUNT or 7),
                encoding="utf-8",
                utc=False,
            )
            fh.setFormatter(fmt)
            fh.setLevel(level)
            root.addHandler(fh)
    except Exception:
        pass

    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
