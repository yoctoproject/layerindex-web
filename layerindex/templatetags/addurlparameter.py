# Borrowed from http://djangosnippets.org/snippets/361/
# Original author: johan de taeye
# With modifications from Ludwik Trammer
#
# Adds GET parameters to the current URL

from django.template import Library, Node, resolve_variable, TemplateSyntaxError, Variable

register = Library()

class AddParameter(Node):
    def __init__(self, varname, value):
        self.varname = Variable(varname)
        self.value = Variable(value)

    def render(self, context):
        req = Variable('request').resolve(context)
        params = req.GET.copy()
        params[self.varname.resolve(context)] = self.value.resolve(context)
        return '%s?%s' % (req.path, params.urlencode())

def addurlparameter(parser, token):
    from re import split
    bits = split(r'\s+', token.contents, 2)
    if len(bits) < 2:
        raise TemplateSyntaxError, "'%s' tag requires two arguments" % bits[0]
    return AddParameter(bits[1],bits[2])

register.tag('addurlparameter', addurlparameter)
