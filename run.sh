#!/bin/bash
# Launch the menu bar app.
cd "$(dirname "$0")"
exec ./.venv/bin/python menubar_flash.py "$@"
