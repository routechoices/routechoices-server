from django.dispatch import Signal

invite_url_sent = Signal()
invite_accepted = Signal()

"""
@receiver(invite_url_sent, sender=Invitation)
def invite_url_sent(sender, instance, invite_url_sent, inviter, **kwargs):
    pass
"""
