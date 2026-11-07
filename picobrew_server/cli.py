"""`picobrew-server` command: run the server with gunicorn and the bundled settings."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from picobrew_server.utils.constants import DATA_DIR_ENV

GUNICORN_CONFIG = "python:picobrew_server.gunicorn_config"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="picobrew-server",
        description="Run the local PicoBrew Zymatic server.",
        epilog="Set SECRET_KEY to keep web sessions valid across restarts. "
        "Other gunicorn settings can be passed through the GUNICORN_CMD_ARGS environment variable.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on (default: %(default)s)")
    parser.add_argument(
        "--port", type=int, default=80, help="port to listen on; the machine always uses 80 (default: %(default)s)"
    )
    parser.add_argument("--workers", type=int, default=2, help="number of worker processes (default: %(default)s)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=os.environ.get(DATA_DIR_ENV) or ".",
        help=f"directory for recipes, sessions and machines; also set by {DATA_DIR_ENV} "
        "(default: the working directory)",
    )
    return parser.parse_args(argv)


def gunicorn_argv(args: argparse.Namespace) -> list[str]:
    host = f"[{args.host}]" if ":" in args.host and not args.host.startswith("[") else args.host
    return ["--config", GUNICORN_CONFIG, "--bind", f"{host}:{args.port}", "--workers", str(args.workers)]


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # Workers create the app after this, so they read the absolute data directory from the environment.
    os.environ[DATA_DIR_ENV] = str(args.data_dir.expanduser().resolve())

    from gunicorn.app.wsgiapp import WSGIApplication

    sys.argv = ["picobrew-server", *gunicorn_argv(args)]
    WSGIApplication("%(prog)s [OPTIONS]", prog="picobrew-server").run()


if __name__ == "__main__":
    main()
