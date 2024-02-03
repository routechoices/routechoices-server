import signal
import sys

from django.core.management.base import BaseCommand
from tornado.ioloop import IOLoop

from routechoices.lib.tcp_protocols import (
    gt06,
    mictrack,
    queclink,
    tmt250,
    tracktape,
    xexun,
)


def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)


class Command(BaseCommand):
    help = "Run a TCP server for GPS trackers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--gt06-port", nargs="?", type=int, help="GT06 Handler Port"
        )
        parser.add_argument(
            "--mictrack-port", nargs="?", type=int, help="Mictrack Handler Port"
        )
        parser.add_argument(
            "--queclink-port", nargs="?", type=int, help="Queclink Handler Port"
        )
        parser.add_argument(
            "--xexun-port", nargs="?", type=int, help="Xexun Handler Port"
        )
        parser.add_argument(
            "--tmt250-port", nargs="?", type=int, help="Teltonika Handler Port"
        )
        parser.add_argument(
            "--tracktape-port", nargs="?", type=int, help="Tracktape Handler Port"
        )

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, sigterm_handler)
        if options.get("gt06_port"):
            gt06_server = gt06.GT06Server()
            gt06_server.listen(options["gt06_port"])
        if options.get("mictrack_port"):
            mictrack_server = mictrack.MicTrackServer()
            mictrack_server.listen(options["mictrack_port"])
        if options.get("queclink_port"):
            queclink_server = queclink.QueclinkServer()
            queclink_server.listen(options["queclink_port"])
        if options.get("tmt250_port"):
            tmt250_server = tmt250.TMT250Server()
            tmt250_server.listen(options["tmt250_port"])
        if options.get("tracktape_port"):
            tracktape_server = tracktape.TrackTapeServer()
            tracktape_server.listen(options["tracktape_port"])
        if options.get("xexun_port"):
            xexun_server = xexun.XexunServer()
            xexun_server.listen(options["xexun_port"])
        try:
            print("Start listening TCP data...", flush=True)
            IOLoop.current().start()
        except (KeyboardInterrupt, SystemExit):
            if options.get("gt06_port"):
                gt06_server.stop()
            if options.get("mictrack_port"):
                mictrack_server.stop()
            if options.get("queclink_port"):
                queclink_server.stop()
            if options.get("tmt250_port"):
                tmt250_server.stop()
            if options.get("tracktape_port"):
                tracktape_server.stop()
            if options.get("xexun_port"):
                xexun_server.stop()
            IOLoop.current().stop()
        finally:
            print("Stopped listening TCP data...", flush=True)
