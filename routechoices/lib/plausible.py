import requests
from django.conf import settings


def domain_is_setup(domain):
    if not settings.ANALYTICS_API_KEY:
        return False
    r = requests.get(
        f"{settings.ANALYTICS_API_URL}/sites/{domain}",
        headers={"authorization": f"Bearer {settings.ANALYTICS_API_KEY}"},
        timeout=5,
    )
    return r.status_code == 200


def create_domain(domain):
    if not settings.ANALYTICS_API_KEY:
        return False
    r = requests.post(
        f"{settings.ANALYTICS_API_URL}/sites",
        headers={"authorization": f"Bearer {settings.ANALYTICS_API_KEY}"},
        data={"domain": domain},
        timeout=5,
    )
    return r.status_code == 200


def create_shared_link(domain, name):
    if not settings.ANALYTICS_API_KEY:
        return "", False
    if not domain_is_setup(domain):
        if not create_domain(domain):
            return "", False
    r = requests.put(
        f"{settings.ANALYTICS_API_URL}/sites/shared-links",
        headers={"authorization": f"Bearer {settings.ANALYTICS_API_KEY}"},
        data={
            "name": name,
            "site_id": domain,
        },
        timeout=5,
    )
    if r.status_code == 200:
        data = r.json()
        return data.get("url", ""), True
    return "", False


def change_domain(from_domain, to_domain):
    if not settings.ANALYTICS_API_KEY:
        return False
    r = requests.put(
        f"{settings.ANALYTICS_API_URL}/sites/{from_domain}",
        headers={"authorization": f"Bearer {settings.ANALYTICS_API_KEY}"},
        data={"domain": to_domain},
        timeout=5,
    )
    return r.status_code == 200


def delete_domain(domain):
    if not settings.ANALYTICS_API_KEY:
        return False
    r = requests.delete(
        f"{settings.ANALYTICS_API_URL}/sites/{domain}",
        headers={"authorization": f"Bearer {settings.ANALYTICS_API_KEY}"},
        timeout=5,
    )
    return r.status_code == 200
