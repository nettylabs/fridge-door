#!/usr/bin/env python3
"""Fridge Door toolkit. Usage: python3 fridge.py <command> [options]   (try: python3 fridge.py --help)

Standard library only (Python 3.9+). Reads and writes local files in your data folder; makes no network
connections.
"""

import json
import os
import sys

if sys.version_info < (3, 9):
    sys.stdout.write(json.dumps({"ok": False, "error": "Fridge Door needs Python 3.9 or newer."}) + "\n")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fridgedoor.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
