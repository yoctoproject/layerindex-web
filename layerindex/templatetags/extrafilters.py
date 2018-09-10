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
    return utils.timesince2(date, date2)
