import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_REQUEST_ID: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


_STRUCTURED_FIELDS = (
    "event",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "rfq_status",
    "customer_id",
    "model",
    "model_response_id",
    "model_latency_ms",
    "estimated_cost_usd",
)


class RequestContextFilter(logging.Filter):
    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(
                record,
                "request_id",
                None,
            ),
        }

        for field in _STRUCTURED_FIELDS:
            value = getattr(
                record,
                field,
                None,
            )

            if value is not None:
                payload[field] = value

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def configure_logging(
    level: int = logging.INFO,
) -> None:
    logger = logging.getLogger("rfq_intelligence")

    logger.handlers.clear()

    handler = logging.StreamHandler()

    handler.addFilter(RequestContextFilter())

    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def get_logger(
    name: str,
) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(
    request_id: str,
) -> Token[str | None]:
    return _REQUEST_ID.set(request_id)


def reset_request_id(
    token: Token[str | None],
) -> None:
    _REQUEST_ID.reset(token)


def get_request_id() -> str | None:
    return _REQUEST_ID.get()
