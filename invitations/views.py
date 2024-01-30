from allauth.account.models import EmailAddress
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin

from .adapters import get_invitations_adapter
from .app_settings import app_settings
from .signals import invite_accepted
from .utils import get_invitation_model, get_invite_form

Invitation = get_invitation_model()
InviteForm = get_invite_form()


class AcceptInvite(SingleObjectMixin, View):
    form_class = InviteForm

    def get_login_redirect(self):
        return app_settings.LOGIN_REDIRECT

    def get_signup_redirect(self):
        return app_settings.SIGNUP_REDIRECT

    def get(self, *args, **kwargs):
        self.object = invitation = self.get_object()
        target_user = True
        if (
            self.request.user.is_authenticated
            and not EmailAddress.objects.filter(
                user=self.request.user, email=invitation.email
            ).exists()
        ):
            target_user = False
        return render(
            self.request,
            "site/invitation.html",
            {"invitation": invitation, "target_user": target_user},
        )

    def post(self, *args, **kwargs):
        self.object = invitation = self.get_object()

        # No invitation was found.
        if not invitation:
            # Newer behavior: show an error message and redirect.
            get_invitations_adapter().add_message(
                self.request,
                messages.ERROR,
                "invitations/messages/invite_invalid.txt",
            )
            return redirect(app_settings.LOGIN_REDIRECT)

        # The invitation was previously accepted, redirect to the login
        # view.
        if invitation.accepted:
            get_invitations_adapter().add_message(
                self.request,
                messages.ERROR,
                "invitations/messages/invite_already_accepted.txt",
                {"email": invitation.email, "club": invitation.club},
            )
            # Redirect to login since there's hopefully an account already.
            return redirect(app_settings.LOGIN_REDIRECT)

        # The key was expired.
        if invitation.key_expired():
            get_invitations_adapter().add_message(
                self.request,
                messages.ERROR,
                "invitations/messages/invite_expired.txt",
                {"email": invitation.email, "club": invitation.club},
            )
            # Redirect to sign-up since they might be able to register anyway.
            return redirect(self.get_signup_redirect())

        if self.request.user.is_authenticated:
            if EmailAddress.objects.filter(
                user=self.request.user, email=invitation.email
            ).exists():
                accept_invitation(
                    invitation=invitation,
                    request=self.request,
                    signal_sender=self.__class__,
                )
                return redirect("dashboard:club_select_view")
            get_invitations_adapter().stash_verified_email(
                self.request, invitation.email
            )
            get_invitations_adapter().add_message(
                self.request,
                messages.ERROR,
                "invitations/messages/invite_for_other.txt",
                {"email": invitation.email, "club": invitation.club},
            )
            return redirect("site:account_logout")

        get_invitations_adapter().stash_verified_email(self.request, invitation.email)

        if EmailAddress.objects.filter(email__iexact=invitation.email):
            return redirect(self.get_login_redirect())

        return redirect(self.get_signup_redirect())

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        try:
            return queryset.get(key=self.kwargs["key"].lower())
        except Invitation.DoesNotExist:
            return None

    def get_queryset(self):
        return Invitation.objects.all()


def accept_invitation(invitation, request, signal_sender):
    invitation.accepted = True
    invitation.save()

    invite_accepted.send(
        sender=signal_sender,
        email=invitation.email,
        request=request,
        invitation=invitation,
    )

    user_email = EmailAddress.objects.filter(email__iexact=invitation.email).first()
    if user_email:
        user = user_email.user
        club = invitation.club
        club.admins.add(user)
        club.save()

    get_invitations_adapter().add_message(
        request,
        messages.SUCCESS,
        "invitations/messages/invite_accepted.txt",
        {"email": invitation.email, "club": invitation.club},
    )


def notice_invitation(invitation, request, signal_sender):
    get_invitations_adapter().add_message(
        request,
        messages.INFO,
        "invitations/messages/invite_sent.txt",
        {"email": invitation.email, "club": invitation.club},
    )


def accept_invite_after_signup(sender, request, user, **kwargs):
    invitations = Invitation.objects.all_valid().filter(
        email__iexact=user.email, accepted=False
    )
    for invitation in invitations:
        accept_invitation(
            invitation=invitation,
            request=request,
            signal_sender=Invitation,
        )


def notice_invites_after_login(sender, request, user, **kwargs):
    invitations = Invitation.objects.all_valid().filter(
        email__iexact=user.email, accepted=False
    )
    for invitation in invitations:
        notice_invitation(
            invitation=invitation,
            request=request,
            signal_sender=Invitation,
        )


signed_up_signal = get_invitations_adapter().get_user_signed_up_signal()
signed_up_signal.connect(accept_invite_after_signup)

logged_in_signal = get_invitations_adapter().get_user_logged_in_signal()
logged_in_signal.connect(notice_invites_after_login)
