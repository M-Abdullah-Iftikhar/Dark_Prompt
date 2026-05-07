#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    # Load variables from .env (next to manage.py) so they're visible to
    # settings.py before Django starts. Silent no-op if python-dotenv isn't
    # installed or .env doesn't exist — settings.py still has env defaults.
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        pass

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "darkprompt.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
