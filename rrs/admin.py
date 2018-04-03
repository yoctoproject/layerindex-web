# rrs-web - admin interface definitions
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter

from rrs.models import Release, Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeDistro, RecipeUpgrade, RecipeUpstream, \
        RecipeUpstreamHistory, MaintenancePlan, MaintenancePlanLayerBranch, \
        RecipeMaintenanceLink

class MaintenancePlanLayerBranchInline(admin.StackedInline):
    model = MaintenancePlanLayerBranch
    readonly_fields = ['upgrade_date', 'upgrade_rev']
    min_num = 1
    extra = 0

class MaintenancePlanAdmin(admin.ModelAdmin):
    model = MaintenancePlan
    inlines = [
        MaintenancePlanLayerBranchInline,
    ]

class ReleaseAdmin(admin.ModelAdmin):
    search_fields = ['name']
    model = Release

class MilestoneAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['release__name']
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

class RecipeMaintenanceLinkAdmin(admin.ModelAdmin):
    model = RecipeMaintenanceLink

admin.site.register(MaintenancePlan, MaintenancePlanAdmin)
admin.site.register(Release, ReleaseAdmin)
admin.site.register(Milestone, MilestoneAdmin)
admin.site.register(Maintainer, MaintainerAdmin)
admin.site.register(RecipeMaintainerHistory, RecipeMaintainerHistoryAdmin)
admin.site.register(RecipeMaintainer, RecipeMaintainerAdmin)
admin.site.register(RecipeDistro, RecipeDistroAdmin)
admin.site.register(RecipeUpgrade, RecipeUpgradeAdmin)
admin.site.register(RecipeUpstreamHistory, RecipeUpstreamHistoryAdmin)
admin.site.register(RecipeUpstream, RecipeUpstreamAdmin)
admin.site.register(RecipeMaintenanceLink, RecipeMaintenanceLinkAdmin)
