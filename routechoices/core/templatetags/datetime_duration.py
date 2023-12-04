import datetime

from django import template
from django.template.defaultfilters import pluralize

register = template.Library()


@register.filter
def duration(value):
    remainder = value
    response = ""
    days = 0
    hours = 0
    minutes = 0
    seconds = 0
    if remainder.days > 0:
        days = remainder.days
        remainder -= datetime.timedelta(days=remainder.days)
    if remainder.seconds // 3600 > 0:
        hours = remainder.seconds // 3600
        remainder -= datetime.timedelta(hours=hours)
    if remainder.seconds // 60 > 0:
        minutes = remainder.seconds // 60
        remainder -= datetime.timedelta(minutes=minutes)
    if remainder.seconds > 0:
        seconds = remainder.seconds
        remainder -= datetime.timedelta(seconds=seconds)

    response = []
    if days:
        response.append(f"{days}day{pluralize(days)} ")
    if hours:
        response.append(f"{hours}h")
    if minutes:
        response.append(f"{minutes}m")
    if seconds:
        response.append(f"{seconds}s")
    response = "".join(response)
    return response
