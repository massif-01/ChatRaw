#!/usr/bin/env python3
"""Run ChatRaw's local Hermes smoke-test double.

This script is only for manual QA and development. ChatRaw never starts it
automatically, and it is not a production Hermes API Server.
"""
import os
import sys


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.hermes_fake_server import main  # noqa: E402


if __name__ == "__main__":
    main()
