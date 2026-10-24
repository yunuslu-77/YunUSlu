"""Entry point of the packaged app: first run opens the setup wizard, later runs open the web interface."""

import sys

from yworkspace.cli import main
from yworkspace.config import home

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = ["web"] if (home() / "setup.json").exists() else ["setup"]
    sys.exit(main(args))
