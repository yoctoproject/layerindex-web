# layerindex-web - middleware definitions
#
# Copyright (C) 2019 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from reversion.middleware import RevisionMiddleware

class NonAtomicRevisionMiddleware(RevisionMiddleware):
    atomic = False


class RejectNullCharactersMiddleware:
    """
    Return a 400 for a request with a NUL character in its path or query
    string. PostgreSQL text can't hold NUL, so any lookup with such a value
    raised DataError and gave a 500. Forms already reject NUL in what they
    clean; this covers the views that read the URL directly.
    (AI-generated, Claude Opus 5.5)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if '\x00' in request.path or any(
                '\x00' in key or any('\x00' in value for value in values)
                for key, values in request.GET.lists()):
            return HttpResponseBadRequest('NUL characters are not allowed')
        return self.get_response(request)
