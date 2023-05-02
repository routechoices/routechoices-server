from django.contrib import admin

from .utils import (
    get_invitation_admin_add_form,
    get_invitation_admin_change_form,
    get_invitation_model,
)

Invitation = get_invitation_model()
InvitationAdminAddForm = get_invitation_admin_add_form()
InvitationAdminChangeForm = get_invitation_admin_change_form()


class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "club", "sent", "accepted")
    raw_id_fields = ("inviter",)
    actions = ["resend"]

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            kwargs["form"] = InvitationAdminChangeForm
        else:
            kwargs["form"] = InvitationAdminAddForm
            kwargs["form"].user = request.user
            kwargs["form"].request = request
        return super().get_form(request, obj, **kwargs)

    def resend(self, request, queryset):
        for obj in queryset:
            if not obj.sent:
                obj.send_invitation(request)

    resend.short_description = "Resend invitations"


admin.site.register(Invitation, InvitationAdmin)
