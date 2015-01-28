# rrs-web - admin interface definitions
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter

from rrs.models import Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeDistro, RecipeUpgrade, RecipeUpstream, \
        RecipeUpstreamHistory

class MilestoneAdmin(admin.ModelAdmin):
    search_fields = ['name']
    model = Milestone

class MaintainerAdmin(admin.ModelAdmin):
    search_fields = ['name']
    model = Maintainer

class RecipeMaintainerHistoryAdmin(admin.ModelAdmin):
    search_fields = ['title', 'author__name', 'sha1']
    list_filter = ['author__name', ('date', DateFieldListFilter)]
    model = RecipeMaintainerHistory

class RecipeMaintainerAdmin(admin.ModelAdmin):
    search_fields = ['recipe__pn']
    list_filter = ['recipe__layerbranch__layer__name', 'history', 'maintainer__name']
    model = RecipeMaintainer

class RecipeDistroAdmin(admin.ModelAdmin):
    search_fields = ['recipe__pn']
    list_filter = ['recipe__layerbranch__layer__name', 'distro']
    model = RecipeDistro

class RecipeUpgradeAdmin(admin.ModelAdmin):
    search_fields = ['recipe__pn']
    list_filter = ['recipe__layerbranch__layer__name',
            ('commit_date', DateFieldListFilter), 'maintainer__name']
    model = RecipeUpgrade

class RecipeUpstreamHistoryAdmin(admin.ModelAdmin):
    list_filter = [
            ('start_date', DateFieldListFilter),
            ('end_date', DateFieldListFilter)
    ]
    model = RecipeUpstreamHistory

class RecipeUpstreamAdmin(admin.ModelAdmin):
    search_fields = ['recipe__pn']
    list_filter = ['recipe__layerbranch__layer__name', 'status',
            'type', ('date', DateFieldListFilter), 'history']
    model = RecipeUpstream

admin.site.register(Milestone, MilestoneAdmin)
admin.site.register(Maintainer, MaintainerAdmin)
admin.site.register(RecipeMaintainerHistory, RecipeMaintainerHistoryAdmin)
admin.site.register(RecipeMaintainer, RecipeMaintainerAdmin)
admin.site.register(RecipeDistro, RecipeDistroAdmin)
admin.site.register(RecipeUpgrade, RecipeUpgradeAdmin)
admin.site.register(RecipeUpstreamHistory, RecipeUpstreamHistoryAdmin)
admin.site.register(RecipeUpstream, RecipeUpstreamAdmin)
