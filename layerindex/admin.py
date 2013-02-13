# layerindex-web - admin interface definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import *
from django.contrib import admin

admin.site.register(LayerItem)
admin.site.register(LayerMaintainer)
admin.site.register(LayerDependency)
admin.site.register(LayerNote)
admin.site.register(Recipe)
