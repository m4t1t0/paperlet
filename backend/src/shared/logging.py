"""Logging configuration with JSON structured logs."""

from __future__ import annotations
import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any

from flask import g, has_request_context, request


class JsonFormatter(logging.Formatter):
    """JSON log formatter with request context."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context if available
        if has_request_context():
            log_data["request_id"] = getattr(g, "request_id", None)
            log_data["trace_id"] = (
                request.headers.get("X-Trace-ID")
                or request.headers.get("traceparent", "").split("-")[0]
                if "-" in request.headers.get("traceparent", "")
                else None
            )
            log_data["user_id"] = getattr(g, "user_id", None)
            log_data["method"] = request.method
            log_data["path"] = request.path
            log_data["ip"] = request.remote_addr

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "getMessage",
            }:
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def setup_logging(app) -> None:
    """Configure JSON structured logging for the Flask app."""
    # Remove default handlers
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)

    # Create JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # Also configure root logger
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def inject_request_id() -> None:
    """Middleware to inject request_id into Flask g object."""
    if not hasattr(g, "request_id"):
        g.request_id = str(uuid.uuid4())
