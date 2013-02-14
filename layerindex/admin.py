# layerindex-web - admin interface definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import *
from django.contrib import admin
from reversion_compare.admin import CompareVersionAdmin

class LayerItemAdmin(CompareVersionAdmin):
    """ Admin settings here """

class LayerMaintainerAdmin(CompareVersionAdmin):
    """ Admin settings here """

class LayerDependencyAdmin(CompareVersionAdmin):
    """ Admin settings here """

class LayerNoteAdmin(CompareVersionAdmin):
    """ Admin settings here """

admin.site.register(LayerItem, LayerItemAdmin)
admin.site.register(LayerMaintainer, LayerMaintainerAdmin)
admin.site.register(LayerDependency, LayerDependencyAdmin)
admin.site.register(LayerNote, LayerNoteAdmin)
admin.site.register(Recipe)
