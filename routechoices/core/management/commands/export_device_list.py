from django.core.management.base import BaseCommand

from routechoices.core.models import Club, DeviceClubOwnership, ImeiDevice


class Command(BaseCommand):
    help = "Export club's device list"

    def add_arguments(self, parser):
        parser.add_argument("club_slug", nargs=1, type=str)

    def handle(self, *args, **options):
        club = Club.objects.filter(slug=options.get("club_slug")[0]).first()
        if not club:
            self.stderr.write(f"No such club: {options.get('club_slug')[0]}")
            return

        self.stdout.write("Nickname;Device ID;IMEI\n")

        devices_qs = DeviceClubOwnership.objects.filter(club_id=club.id).select_related(
            "device"
        )
        devices = {
            own.device.aid: {"nickname": own.nickname, "aid": own.device.aid}
            for own in devices_qs
        }
        imeis = ImeiDevice.objects.filter(
            device_id__in=[device.device.id for device in devices_qs]
        )
        for imei in imeis:
            devices[imei.device.aid]["imei"] = imei.imei
        for dev in devices.values():
            self.stdout.write(
                f'{dev.get("nickname")};{dev.get("aid")};{dev.get("imei", "")}\n'
            )
