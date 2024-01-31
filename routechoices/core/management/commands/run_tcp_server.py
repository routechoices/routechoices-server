import logging
import os.path
import signal
import sys

import arrow
from django.conf import settings
from django.core.management.base import BaseCommand
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer

from routechoices.lib.tcp_protocols import (
    GT06Connection,
    MicTrackConnection,
    QueclinkConnection,
    TK201Connection,
    TMT250Connection,
    TrackTapeConnection,
)

logger = logging.getLogger("TCP Rotating Log")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    os.path.join(settings.BASE_DIR, "logs", "tcp.log"), maxBytes=10000000, backupCount=5
)
logger.addHandler(handler)


def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)


class GenericTCPServer(TCPServer):
    connection_class = None

    async def handle_stream(self, stream, address):
        if not self.connection_class:
            return
        c = self.connection_class(stream, address, logger)
        try:
            await c.start_listening()
        except StreamClosedError:
            pass


class GT06Server(GenericTCPServer):
    connection_class = GT06Connection


class MicTrackServer(GenericTCPServer):
    connection_class = MicTrackConnection


class TMT250Server(GenericTCPServer):
    connection_class = TMT250Connection


class QueclinkServer(GenericTCPServer):
    connection_class = QueclinkConnection


class TrackTapeServer(GenericTCPServer):
    connection_class = TrackTapeConnection


class TK201Server(GenericTCPServer):
    connection_class = TK201Connection


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
            "--tk201-port", nargs="?", type=int, help="TK201 Handler Port"
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
            gt06_server = GT06Server()
            gt06_server.listen(options["gt06_port"])
        if options.get("tmt250_port"):
            tmt250_server = TMT250Server()
            tmt250_server.listen(options["tmt250_port"])
        if options.get("queclink_port"):
            queclink_server = QueclinkServer()
            queclink_server.listen(options["queclink_port"])
        if options.get("mictrack_port"):
            mictrack_server = MicTrackServer()
            mictrack_server.listen(options["mictrack_port"])
        if options.get("tracktape_port"):
            tracktape_server = TrackTapeServer()
            tracktape_server.listen(options["tracktape_port"])
        if options.get("tk201_port"):
            tk201_server = TK201Server()
            tk201_server.listen(options["tk201_port"])
        try:
            print("Start listening TCP data...", flush=True)
            logger.info(f"{arrow.now().datetime}, UP")
            IOLoop.current().start()
        except (KeyboardInterrupt, SystemExit):
            if options.get("gt06_port"):
                gt06_server.stop()
            if options.get("tmt250_port"):
                tmt250_server.stop()
            if options.get("queclink_port"):
                queclink_server.stop()
            if options.get("mictrack_port"):
                mictrack_server.stop()
            if options.get("tracktape_port"):
                tracktape_server.stop()
            if options.get("tk201_port"):
                tk201_server.stop()
            IOLoop.current().stop()
        finally:
            print("Stopped listening TCP data...", flush=True)
            logger.info(f"{arrow.now().datetime}, DOWN")
            logging.shutdown()
