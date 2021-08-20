from django import forms

from admincommand.models import AdminCommand


class ImportFromGpsseuranta(AdminCommand):

    class form(forms.Form):
        event_id = forms.CharField()

    def get_command_arguments(self, forms_data, user):
        return [forms_data['event_id']], {'task': True}


class ImportFromLoggator(AdminCommand):

    class form(forms.Form):
        event_id = forms.CharField()

    def get_command_arguments(self, forms_data, user):
        return [forms_data['event_id']], {'task': True}


class ImportFromTractrac(AdminCommand):

    class form(forms.Form):
        event_id = forms.CharField()

    def get_command_arguments(self, forms_data, user):
        return [forms_data['event_id']], {'task': True}


class ImportFromSportrec(AdminCommand):

    class form(forms.Form):
        event_id = forms.CharField()

    def get_command_arguments(self, forms_data, user):
        return [forms_data['event_id']], {'task': True}


class ImportFromOtracker(AdminCommand):

    class form(forms.Form):
        event_id = forms.CharField()

    def get_command_arguments(self, forms_data, user):
        return [forms_data['event_id']], {'task': True}
