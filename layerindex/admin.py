# layerindex-web - admin interface definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import *
from django.contrib import admin
from reversion_compare.admin import CompareVersionAdmin
from django.forms import TextInput

class LayerMaintainerInline(admin.StackedInline):
    model = LayerMaintainer

class LayerDependencyInline(admin.StackedInline):
    model = LayerDependency
    fk_name = 'layer'

class LayerItemAdmin(CompareVersionAdmin):
    list_filter = ['status', 'layer_type']
    save_as = True
    search_fields = ['name', 'summary']
    readonly_fields = ['vcs_last_fetch', 'vcs_last_rev', 'vcs_last_commit']
    formfield_overrides = {
        models.URLField: {'widget': TextInput(attrs={'size':'100'})},
        models.CharField: {'widget': TextInput(attrs={'size':'100'})},
    }
    inlines = [
        LayerMaintainerInline,
        LayerDependencyInline,
    ]

class LayerMaintainerAdmin(CompareVersionAdmin):
    list_filter = ['status', 'layer__name']

class LayerDependencyAdmin(CompareVersionAdmin):
    list_filter = ['layer__name']

class LayerNoteAdmin(CompareVersionAdmin):
    list_filter = ['layer__name']

class RecipeAdmin(admin.ModelAdmin):
    search_fields = ['filename', 'pn']
    list_filter = ['layer__name']
    readonly_fields = Recipe._meta.get_all_field_names()
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(LayerItem, LayerItemAdmin)
admin.site.register(LayerMaintainer, LayerMaintainerAdmin)
admin.site.register(LayerDependency, LayerDependencyAdmin)
admin.site.register(LayerNote, LayerNoteAdmin)
admin.site.register(Recipe, RecipeAdmin)
