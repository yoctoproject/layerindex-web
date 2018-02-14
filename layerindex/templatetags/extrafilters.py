from django import template
from .. import utils

register = template.Library()

@register.filter
def replace_commas(string):
    return string.replace(',', '_')

@register.filter
def squashspaces(strval):
    return utils.squashspaces(strval)
