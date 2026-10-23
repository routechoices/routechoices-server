from functools import wraps
from inspect import signature

from rest_framework.test import APIClient as RestFrameworkAPIClient
from rest_framework.test import APITestCase as RestFrameworkAPITestCase


def _secure_by_default(method):
    method_signature = signature(method)

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if (
            "secure" not in kwargs
            and "secure"
            not in method_signature.bind_partial(self, *args, **kwargs).arguments
        ):
            kwargs["secure"] = True
        return method(self, *args, **kwargs)

    return wrapped


class APIClient(RestFrameworkAPIClient):
    generic = _secure_by_default(RestFrameworkAPIClient.generic)
    get = _secure_by_default(RestFrameworkAPIClient.get)
    post = _secure_by_default(RestFrameworkAPIClient.post)
    head = _secure_by_default(RestFrameworkAPIClient.head)
    options = _secure_by_default(RestFrameworkAPIClient.options)
    put = _secure_by_default(RestFrameworkAPIClient.put)
    patch = _secure_by_default(RestFrameworkAPIClient.patch)
    delete = _secure_by_default(RestFrameworkAPIClient.delete)
    trace = _secure_by_default(RestFrameworkAPIClient.trace)


class APITestCase(RestFrameworkAPITestCase):
    client_class = APIClient
