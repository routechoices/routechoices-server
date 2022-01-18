#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    argv = sys.argv
    try:
        command = argv[1]
    except IndexError:
        argv[1] = "help"
    if command == "test":
        default = "routechoices.test_settings"
    else:
        default = "routechoices.settings"

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(argv)
