"""Minimal entrypoint for MCP Orchestrator with basic logging and PID-file support."""
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from orchestrator.mcp_client import MCPClient

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "orchestrator.log")


def setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    fh = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)


def _write_pidfile(path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        logging.exception("Failed to write pidfile %s", path)


def _remove_pidfile(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        logging.exception("Failed to remove pidfile %s", path)


def main() -> None:
    setup_logging()
    logging.info("MCP Orchestrator (dev) — starting")

    # Optional PID file path from env var ORCH_PID_FILE
    pidfile = os.environ.get("ORCH_PID_FILE")
    if pidfile:
        _write_pidfile(pidfile)
        logging.info("Wrote pidfile: %s", pidfile)

        # Demo: make a safe MCP client call (mocked when no API key configured)
        try:
            client = MCPClient()
            demo = client.search_restaurants("biryani")
            logging.info("MCPClient demo result: %s", demo)
        except Exception:
            logging.exception("MCPClient demo failed")

    try:
        logging.info("Run: python -m orchestrator; logs at %s", LOG_FILE)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("Shutting down.")
    finally:
        _remove_pidfile(pidfile)


if __name__ == "__main__":
    main()
