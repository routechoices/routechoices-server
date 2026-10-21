import atexit
import sys

import coverage

from .wsgi import application  # noqa


def save_coverage():
    print("Saving coverage", flush=True, file=sys.stderr)
    cov.stop()
    cov.save()


cov = coverage.coverage()
cov.start()
atexit.register(save_coverage)
