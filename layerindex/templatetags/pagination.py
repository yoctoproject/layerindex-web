# Borrowed from http://djangosnippets.org/snippets/2199/
#
# Digg-like page numbering using inclusion tag

from django import template

register = template.Library()

@register.inclusion_tag('pagination.html', takes_context=True)
def pagination(context, page, begin_pages=2, end_pages=2, before_current_pages=4, after_current_pages=4):
    # Digg-like pages
    before = max(page.number - before_current_pages - 1, 0)
    after = page.number + after_current_pages

    begin = page.paginator.page_range[:begin_pages]
    middle = page.paginator.page_range[before:after]
    end = page.paginator.page_range[-end_pages:]
    last_page_number = end[-1]

    def collides(firstlist, secondlist):
        """ Returns true if lists collides (have same entries)

        >>> collides([1,2,3,4],[3,4,5,6,7])
        True
        >>> collides([1,2,3,4],[5,6,7])
        False
        """
        return any(item in secondlist for item in firstlist)

    # If middle and end has same entries, then end is what we want
    if collides(middle, end):
        end = range(max(page.number-before_current_pages, 1), last_page_number+1)

        middle = []

    # If begin and middle ranges has same entries, then begin is what we want
    if collides(begin, middle):
        begin = range(1, min(page.number + after_current_pages, last_page_number)+1)

        middle = []

    # If begin and end has same entries then begin is what we want
    if collides(begin, end):
        begin = range(1, last_page_number+1)
        end = []

    context.update({'page' : page,
                    'begin' : begin,
                    'middle' : middle,
                    'end' : end})

    return context
