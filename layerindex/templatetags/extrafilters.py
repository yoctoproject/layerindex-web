from datetime import datetime
from django import template
from .. import utils

register = template.Library()

@register.filter
def replace_commas(string):
    return string.replace(',', '_')

@register.filter
def squashspaces(strval):
    return utils.squashspaces(strval)

@register.filter
def truncatesimple(strval, length):
    return strval[:length]

@register.filter
def timesince2(date, date2=None):
    # Based on http://www.didfinishlaunchingwithoptions.com/a-better-timesince-template-filter-for-django/
    if date2 is None:
        date2 = datetime.now()
    if date > date2:
        return '0 seconds'
    diff = date2 - date
    periods = (
        (diff.days // 365, 'year', 'years'),
        (diff.days // 30, 'month', 'months'),
        (diff.days // 7, 'week', 'weeks'),
        (diff.days, 'day', 'days'),
        (diff.seconds // 3600, 'hour', 'hours'),
        (diff.seconds // 60, 'minute', 'minutes'),
        (diff.seconds, 'second', 'seconds'),
    )
    for period, singular, plural in periods:
        if period:
            return '%d %s' % (period, singular if period == 1 else plural)
    return '0 seconds'
