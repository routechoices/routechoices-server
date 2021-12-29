from rest_framework.authentication import SessionAuthentication 


def true(r):
    return True


class CsrfExemptSessionAuthentication(SessionAuthentication):

    def enforce_csrf(self, request):
        return  False