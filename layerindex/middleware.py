# layerindex-web - middleware definitions
#
# Copyright (C) 2019 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from reversion.middleware import RevisionMiddleware
import settings
import re

class NonAtomicRevisionMiddleware(RevisionMiddleware):
    atomic = False
