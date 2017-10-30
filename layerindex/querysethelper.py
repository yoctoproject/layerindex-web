import operator
import functools
from django.db.models import Q, CharField

def _verify_parameters(g, mandatory_parameters):
    miss = []
    for mp in mandatory_parameters:
        if not mp in g:
            miss.append(mp)
    if len(miss):
        return miss
    return None

def _redirect_parameters(view, g, mandatory_parameters, *args, **kwargs):
    import urllib
    url = reverse(view, kwargs=kwargs)
    params = {}
    for i in g:
        params[i] = g[i]
    for i in mandatory_parameters:
        if not i in params:
            params[i] = mandatory_parameters[i]

    return redirect(url + "?%s" % urllib.urlencode(params), *args, **kwargs)

FIELD_SEPARATOR = ":"
VALUE_SEPARATOR = "!"
DESCENDING = "-"

def __get_q_for_val(name, value):
    if "OR" in value:
        return functools.reduce(operator.or_, map(lambda x: __get_q_for_val(name, x), [ x for x in value.split("OR") ]))
    if "AND" in value:
        return functools.reduce(operator.and_, map(lambda x: __get_q_for_val(name, x), [ x for x in value.split("AND") ]))
    if value.startswith("NOT"):
        kwargs = { name : value.strip("NOT") }
        return ~Q(**kwargs)
    else:
        kwargs = { name : value }
        return Q(**kwargs)

def _get_filtering_query(filter_string):

    search_terms = filter_string.split(FIELD_SEPARATOR)
    keys = search_terms[0].split(VALUE_SEPARATOR)
    values = search_terms[1].split(VALUE_SEPARATOR)

    querydict = dict(zip(keys, values))
    return functools.reduce(operator.and_, map(lambda x: __get_q_for_val(x, querydict[x]), [k for k in querydict]))

# we check that the input comes in a valid form that we can recognize
def _validate_input(input, model):

    invalid = None

    if input:
        input_list = input.split(FIELD_SEPARATOR)

        # Check we have only one colon
        if len(input_list) != 2:
            invalid = "We have an invalid number of separators: " + input + " -> " + str(input_list)
            return None, invalid

        # Check we have an equal number of terms both sides of the colon
        if len(input_list[0].split(VALUE_SEPARATOR)) != len(input_list[1].split(VALUE_SEPARATOR)):
            invalid = "Not all arg names got values"
            return None, invalid + str(input_list)

        # Check we are looking for a valid field
        valid_fields = model._meta.get_all_field_names()
        for field in input_list[0].split(VALUE_SEPARATOR):
            if not functools.reduce(lambda x, y: x or y, map(lambda x: field.startswith(x), [ x for x in valid_fields ])):
                return None, (field, [ x for x in valid_fields ])

    return input, invalid

# uses search_allowed_fields in orm/models.py to create a search query
# for these fields with the supplied input text
def _get_search_results(search_term, queryset, model):
    search_objects = []
    for st in search_term.split(" "):
        if hasattr(model, 'search_allowed_fields'):
            fieldlist = model.search_allowed_fields
        else:
            fieldlist = [f.name for f in model._meta.get_fields() if isinstance(f, CharField)]
        q_map = map(lambda x: Q(**{x+'__icontains': st}),
                fieldlist)

        search_objects.append(functools.reduce(operator.or_, q_map))
    search_object = functools.reduce(operator.and_, search_objects)
    queryset = queryset.filter(search_object)

    return queryset


# function to extract the search/filter/ordering parameters from the request
# it uses the request and the model to validate input for the filter and orderby values
def get_search_tuple(request, model):
    ordering_string, invalid = _validate_input(request.GET.get('orderby', ''), model)
    if invalid:
        raise BaseException("Invalid ordering model:" + str(model) + str(invalid))

    filter_string, invalid = _validate_input(request.GET.get('filter', ''), model)
    if invalid:
        raise BaseException("Invalid filter " + str(invalid))

    search_term = request.GET.get('search', '')
    return (filter_string, search_term, ordering_string)


# returns a lazy-evaluated queryset for a filter/search/order combination
def params_to_queryset(model, queryset, filter_string, search_term, ordering_string):
    if filter_string:
        filter_query = _get_filtering_query(filter_string)
        queryset = queryset.filter(filter_query)
    else:
        queryset = queryset.all()

    if search_term:
        queryset = _get_search_results(search_term, queryset, model)

    if ordering_string and queryset:
        column, order = ordering_string.split(':')
        if order.lower() == DESCENDING:
            column = '-' + column

    # insure only distinct records (e.g. from multiple search hits) are returned
    return queryset.distinct()


