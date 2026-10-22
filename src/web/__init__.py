"""MultiCloud Transfer Manager Web App (Flask + Tailwind CSS + shadcn UI)."""

from web.app import create_app, run_server
from web.bridge import WebBridge
from web.cli import main

__all__ = ["WebBridge", "create_app", "main", "run_server"]
