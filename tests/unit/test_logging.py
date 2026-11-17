import json
import logging

from app.core.logging import JsonFormatter


def test_server_exception_log_hides_exception_message() -> None:
    exception = RuntimeError("private-exception-value")
    record = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "private-module-path",
        1,
        "ASGI error: %s",
        (exception,),
        (RuntimeError, exception, None),
    )

    output = JsonFormatter("prd").format(record)

    assert "private-" not in output
    entry = json.loads(output)
    assert entry["message"] == "Unhandled server exception"
    assert entry["severity"] == "ERROR"
