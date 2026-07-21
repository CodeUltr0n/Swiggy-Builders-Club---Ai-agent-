"""Minimal entrypoint for MCP Orchestrator."""
import time


def main() -> None:
    print("MCP Orchestrator (dev) — starting")
    print("Run: python -m orchestrator")
    print("Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Shutting down.")


if __name__ == "__main__":
    main()
