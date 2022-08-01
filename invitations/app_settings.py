from django.conf import settings


class AppSettings:
    def __init__(self, prefix):
        self.prefix = prefix

    def _setting(self, name, dflt):
        return getattr(settings, self.prefix + name, dflt)

    @property
    def INVITATION_EXPIRY(self):
        """How long before the invitation expires"""
        return self._setting("INVITATION_EXPIRY", 3)

    @property
    def INVITATION_ONLY(self):
        """Signup is invite only"""
        return self._setting("INVITATION_ONLY", False)

    @property
    def CONFIRM_INVITE_ON_GET(self):
        """Simple get request confirms invite"""
        return self._setting("CONFIRM_INVITE_ON_GET", False)

    @property
    def GONE_ON_ACCEPT_ERROR(self):
        """
        If an invalid/expired/previously accepted key is provided, return a
        HTTP 410 GONE response.
        """
        return self._setting("GONE_ON_ACCEPT_ERROR", True)

    @property
    def SIGNUP_REDIRECT(self):
        """Where to redirect on email confirm of invite"""
        return self._setting("SIGNUP_REDIRECT", "account_signup")

    @property
    def LOGIN_REDIRECT(self):
        """Where to redirect on an expired or already accepted invite"""
        return self._setting("LOGIN_REDIRECT", settings.LOGIN_URL)

    @property
    def ADAPTER(self):
        """The adapter, setting ACCOUNT_ADAPTER overrides this default"""
        return self._setting("ADAPTER", "invitations.adapters.BaseInvitationsAdapter")

    @property
    def EMAIL_MAX_LENGTH(self):
        """
        Adjust max_length of e-mail addresses
        """
        return self._setting("EMAIL_MAX_LENGTH", 254)

    @property
    def EMAIL_SUBJECT_PREFIX(self):
        """
        Subject-line prefix to use for email messages sent
        """
        return self._setting("EMAIL_SUBJECT_PREFIX", None)

    @property
    def INVITATION_MODEL(self):
        """
        Subject-line prefix to use for Invitation model setup
        """
        return self._setting("INVITATION_MODEL", "invitations.Invitation")

    @property
    def INVITE_FORM(self):
        """
        Form class used for sending invites outside admin.
        """
        return self._setting("INVITE_FORM", "invitations.forms.InviteForm")

    @property
    def ADMIN_ADD_FORM(self):
        """
        Form class used for sending invites in admin.
        """
        return self._setting(
            "ADMIN_ADD_FORM",
            "invitations.forms.InvitationAdminAddForm",
        )

    @property
    def ADMIN_CHANGE_FORM(self):
        """
        Form class used for updating invitations in admin.
        """
        return self._setting(
            "ADMIN_CHANGE_FORM",
            "invitations.forms.InvitationAdminChangeForm",
        )

    @property
    def CONFIRMATION_URL_NAME(self):
        return self._setting("CONFIRMATION_URL_NAME", "invitations:accept-invite")


app_settings = AppSettings("INVITATIONS_")
