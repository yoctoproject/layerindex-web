# rrs-web - admin interface definitions
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.utils.functional import curry

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django import forms
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError

from rrs.models import Release, Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeDistro, RecipeUpgrade, RecipeUpstream, \
        RecipeUpstreamHistory, MaintenancePlan, MaintenancePlanLayerBranch, \
        RecipeMaintenanceLink, RecipeSymbol, RecipeUpgradeGroupRule, \
        RecipeUpgradeGroup

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

    def clean(self):
        super(MaintenancePlanLayerBranchFormSet, self).clean()
        total_checked = 0

        for form in self.forms:
            if not form.is_valid():
                return
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                layerbranch = form.cleaned_data['layerbranch']
                if not layerbranch:
                    raise ValidationError('You must select a layerbranch')
                # Only allow one plan per layer
                # NOTE: This restriction is in place because we don't have enough safeguards in the
                # processing code to avoid processing a layer multiple times if it's part of
                # more than one plan, and there may be other challenges. For now, just keep it simple.
                mplayerbranches = layerbranch.maintenanceplanlayerbranch_set.all()
                if form.instance.pk is not None:
                    mplayerbranches = mplayerbranches.exclude(id=form.instance.id)
                if mplayerbranches.exists():
                    raise ValidationError('A layer branch can only be part of one maintenance plan - layer branch %s is already part of maintenance plan %s' % (layerbranch, mplayerbranches.first().plan.name))
                total_checked += 1


class MaintenancePlanLayerBranchInline(admin.StackedInline):
    model = MaintenancePlanLayerBranch
    formset = MaintenancePlanLayerBranchFormSet
    readonly_fields = ['upgrade_date', 'upgrade_rev']
    min_num = 1
    extra = 0

class MaintenancePlanAdminForm(forms.ModelForm):
    model = MaintenancePlan

    def clean_email_to(self):
        val = self.cleaned_data['email_to']
        if self.cleaned_data['email_enabled']:
            if not val:
                raise ValidationError('To email address must be specified if emails are enabled')
        return val

    def clean_email_from(self):
        val = self.cleaned_data['email_from']
        if self.cleaned_data['email_enabled']:
            if not val:
                raise ValidationError('From email address must be specified if emails are enabled')
        return val

    def clean_email_subject(self):
        val = self.cleaned_data['email_subject']
        if self.cleaned_data['email_enabled']:
            if not val:
                raise ValidationError('Email subject must be specified if emails are enabled')
        return val

class MaintenancePlanAdmin(admin.ModelAdmin):
    model = MaintenancePlan
    form = MaintenancePlanAdminForm
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

class MilestoneFormSet(BaseInlineFormSet):
    def clean(self):
        super(MilestoneFormSet, self).clean()
        total = 0
        for form in self.forms:
            if not form.is_valid():
                return
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                total += 1
        if not total:
            raise ValidationError('Releases must have at least one milestone')

class MilestoneInline(admin.StackedInline):
    model = Milestone
    formset = MilestoneFormSet

class ReleaseAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['plan']
    model = Release
    inlines = [
        MilestoneInline,
    ]

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
    search_fields = ['recipesymbol__pn']
    list_filter = ['recipesymbol__layerbranch__layer__name', 'history', 'maintainer__name']
    model = RecipeMaintainer

class RecipeDistroAdmin(admin.ModelAdmin):
    search_fields = ['recipe__pn']
    list_filter = ['recipe__layerbranch__layer__name', 'distro']
    model = RecipeDistro

class RecipeUpgradeAdmin(admin.ModelAdmin):
    search_fields = ['recipesymbol__pn']
    list_filter = ['recipesymbol__layerbranch__layer__name',
                   'upgrade_type', ('commit_date', DateFieldListFilter),
                   'maintainer__name']
    model = RecipeUpgrade

class RecipeUpstreamHistoryAdmin(admin.ModelAdmin):
    list_filter = [
            'layerbranch__layer',
            ('start_date', DateFieldListFilter),
            ('end_date', DateFieldListFilter)
    ]
    model = RecipeUpstreamHistory

class RecipeUpstreamAdmin(admin.ModelAdmin):
    search_fields = ['recipesymbol__pn']
    list_filter = ['recipesymbol__layerbranch__layer__name', 'status',
            'type', ('date', DateFieldListFilter), 'history']
    model = RecipeUpstream

class RecipeMaintenanceLinkAdmin(admin.ModelAdmin):
    model = RecipeMaintenanceLink

class RecipeSymbolAdmin(admin.ModelAdmin):
    model = RecipeSymbol
    search_fields = ['pn']
    list_filter = ['layerbranch']

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
admin.site.register(RecipeSymbol, RecipeSymbolAdmin)
admin.site.register(RecipeUpgradeGroupRule)
admin.site.register(RecipeUpgradeGroup)
