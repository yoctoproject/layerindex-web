# rrs-web - admin interface definitions
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.utils.functional import curry

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.forms.models import BaseInlineFormSet

from rrs.models import Release, Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeDistro, RecipeUpgrade, RecipeUpstream, \
        RecipeUpstreamHistory, MaintenancePlan, MaintenancePlanLayerBranch, \
        RecipeMaintenanceLink

class MaintenancePlanLayerBranchFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        from layerindex.models import PythonEnvironment
        initialfields = {}
        py2env = PythonEnvironment.get_default_python2_environment()
        if py2env:
            initialfields['python2_environment'] = py2env.id
        py3env = PythonEnvironment.get_default_python3_environment()
        if py3env:
            initialfields['python3_environment'] = py3env.id
        if initialfields:
            kwargs['initial'] = [initialfields]
        super(MaintenancePlanLayerBranchFormSet, self).__init__(*args, **kwargs)

    @property
    def empty_form(self):
        from layerindex.models import PythonEnvironment
        form = super(MaintenancePlanLayerBranchFormSet, self).empty_form
        py2env = PythonEnvironment.get_default_python2_environment()
        if py2env:
            form.fields['python2_environment'].initial = py2env
        py3env = PythonEnvironment.get_default_python3_environment()
        if py3env:
            form.fields['python3_environment'].initial = py3env
        return form

class MaintenancePlanLayerBranchInline(admin.StackedInline):
    model = MaintenancePlanLayerBranch
    formset = MaintenancePlanLayerBranchFormSet
    readonly_fields = ['upgrade_date', 'upgrade_rev']
    min_num = 1
    extra = 0

class MaintenancePlanAdmin(admin.ModelAdmin):
    model = MaintenancePlan
    inlines = [
        MaintenancePlanLayerBranchInline,
    ]
    def save_model(self, request, obj, form, change):
        # For new maintenance plans, copy releases from the first plan
        if obj.pk is None:
            copyfrom_mp = MaintenancePlan.objects.all().first()
        else:
            copyfrom_mp = None
        super().save_model(request, obj, form, change)
        if copyfrom_mp:
            for release in copyfrom_mp.release_set.all():
                release.pk = None
                release.plan = obj
                release.save()
                milestone = Milestone(release=release)
                milestone.name='Default'
                milestone.start_date = release.start_date
                milestone.end_date = release.end_date
                milestone.save()

class ReleaseAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['plan']
    model = Release

class MilestoneAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['release__plan', 'release__name']
    model = Milestone

class MaintainerAdmin(admin.ModelAdmin):
    search_fields = ['name']
    model = Maintainer

class RecipeMaintainerHistoryAdmin(admin.ModelAdmin):
    search_fields = ['title', 'author__name', 'sha1']
    list_filter = ['layerbranch__layer', 'author__name', ('date', DateFieldListFilter)]
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
            'layerbranch__layer',
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
