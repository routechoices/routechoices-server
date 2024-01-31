import time

import arrow
from django.db import DatabaseError

from routechoices.core.models import Device, TcpDeviceCommand


def _get_device(imei):
    try:
        return Device.objects.get(physical_device__imei=imei)
    except DatabaseError:
        from django.db import connections

        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()
        time.sleep(5)
        return _get_device(imei)
    except Exception:
        return None


def _get_pending_commands(imei):
    try:
        commands = list(
            TcpDeviceCommand.objects.filter(target__imei=imei, sent=False).values_list(
                "command", flat=True
            )
        )
        t = arrow.now().datetime
        return t, commands
    except DatabaseError:
        from django.db import connections

        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()
        return None
    except Exception:
        return None


def _mark_pending_commands_sent(imei, max_date):
    try:
        return TcpDeviceCommand.objects.filter(
            target__imei=imei,
            sent=False,
            creation_date__lte=max_date,
        ).update(sent=True, modification_date=arrow.now().datetime)
    except DatabaseError:
        from django.db import connections

        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()
        return 0
    except Exception:
        return 0
