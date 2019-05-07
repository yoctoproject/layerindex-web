# layerindex-web - admin interface definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import *
from django.contrib import admin
from reversion_compare.admin import CompareVersionAdmin
from django.forms import TextInput
from django.contrib.sites.models import Site

class LayerMaintainerInline(admin.StackedInline):
    model = LayerMaintainer

class LayerDependencyInline(admin.StackedInline):
    model = LayerDependency

class BranchAdmin(CompareVersionAdmin):
    model = Branch
    actions = ['duplicate']

    def duplicate(self, request, queryset):
        for branch in queryset:
            layerbranches = branch.layerbranch_set.all()
            branch.pk = None
            branch.name += '-copy'
            branch.save()
            for layerbranch in layerbranches:
                layerbranch_maintainers = layerbranch.layermaintainer_set.all()
                layerbranch_dependencies = layerbranch.dependencies_set.all()
                layerbranch.pk = None
                layerbranch.branch = branch
                layerbranch.vcs_last_fetch = None
                layerbranch.vcs_last_rev = ''
                layerbranch.vcs_last_commit = None
                layerbranch.save()
                for layermaintainer in layerbranch_maintainers:
                    layermaintainer.pk = None
                    layermaintainer.layerbranch = layerbranch
                    layermaintainer.save()
                for layerdependency in layerbranch_dependencies:
                    layerdependency.pk = None
                    layerdependency.layerbranch = layerbranch
                    layerdependency.save()
    duplicate.short_description = "Duplicate selected Branches"

class YPCompatibleVersionAdmin(CompareVersionAdmin):
    pass

class LayerItemAdmin(CompareVersionAdmin):
    list_filter = ['status', 'layer_type']
    save_as = True
    search_fields = ['name', 'summary', 'vcs_url']
    formfield_overrides = {
        models.URLField: {'widget': TextInput(attrs={'size':'100'})},
        models.CharField: {'widget': TextInput(attrs={'size':'100'})},
    }

class LayerBranchAdmin(CompareVersionAdmin):
    list_filter = ['layer__name']
    search_fields = ['layer__name', 'layer__vcs_url']
    readonly_fields = ('vcs_last_fetch', 'vcs_last_rev', 'vcs_last_commit')
    inlines = [
        LayerDependencyInline,
        LayerMaintainerInline,
    ]
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = self.readonly_fields
        if obj:
            readonly_fields += ('layer',)
        if not request.user.has_perm('layerindex.set_yp_compatibility'):
            readonly_fields += ('yp_compatible_version',)
        return readonly_fields

class LayerMaintainerAdmin(CompareVersionAdmin):
    search_fields = ['name', 'email']
    list_filter = ['status', 'layerbranch__layer__name']

class LayerDependencyAdmin(CompareVersionAdmin):
    list_filter = ['layerbranch__layer__name']

class LayerNoteAdmin(CompareVersionAdmin):
    list_filter = ['layer__name']

class UpdateAdmin(admin.ModelAdmin):
    pass

class LayerUpdateAdmin(admin.ModelAdmin):
    list_filter = ['update__started', 'layer', 'branch']

class RecipeAdmin(admin.ModelAdmin):
    search_fields = ['filename', 'pn']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    def get_readonly_fields(self, request, obj=None):
        rofields = []
        for f in Recipe._meta.get_fields():
            if not (f.auto_created and f.is_relation):
                rofields.append(f.name)
        return rofields
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class PackageConfigAdmin(admin.ModelAdmin):
    search_fields = ['feature', 'recipe__pn']
    ordering = ('feature',)

class StaticBuildDepAdmin(admin.ModelAdmin):
    search_fields = ['name']
    filter_horizontal = ('recipes',)

class DynamicBuildDepAdmin(admin.ModelAdmin):
    search_fields = ['name']
    filter_horizontal = ('package_configs',)

class SourceAdmin(admin.ModelAdmin):
    pass

class ClassicRecipeAdmin(admin.ModelAdmin):
    search_fields = ['filename', 'pn', 'cover_pn']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    def get_readonly_fields(self, request, obj=None):
        rofields = []
        for f in ClassicRecipe._meta.get_fields():
            if not (f.auto_created and f.is_relation):
                rofields.append(f.name)
        return rofields
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class MachineAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    readonly_fields = [f.name for f in Machine._meta.get_fields()]
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class DistroAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    readonly_fields = [f.name for f in Distro._meta.get_fields()]
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


class BBAppendAdmin(admin.ModelAdmin):
    search_fields = ['filename']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    readonly_fields = [f.name for f in BBAppend._meta.get_fields()]
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class BBClassAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    readonly_fields = [f.name for f in BBClass._meta.get_fields()]
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class PatchAdmin(admin.ModelAdmin):
    search_fields = ['path']
    list_filter = ['recipe__layerbranch__layer__name', 'recipe__layerbranch__branch__name']
    readonly_fields = [f.name for f in Patch._meta.get_fields()]
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class PatchDispositionAdmin(admin.ModelAdmin):
    fields = ['patch', 'user', 'disposition', 'comment']
    search_fields = ['patch__path']
    list_filter = ['patch__recipe__layerbranch__layer__name', 'patch__recipe__layerbranch__branch__name']
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ['user']
        if obj:
            readonly_fields.append('patch')
            if not (request.user == obj.user or request.user.is_superuser):
                readonly_fields.append('disposition', 'comment')
        return readonly_fields

class IncFileAdmin(admin.ModelAdmin):
    search_fields = ['path']
    list_filter = ['layerbranch__layer__name', 'layerbranch__branch__name']
    readonly_fields = [f.name for f in IncFile._meta.get_fields()]
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class RecipeChangeInline(admin.StackedInline):
    model = RecipeChange

class RecipeChangesetAdmin(admin.ModelAdmin):
    model = RecipeChangeset
    inlines = [
        RecipeChangeInline
    ]

class ComparisonRecipeUpdateAdmin(admin.ModelAdmin):
    model = ComparisonRecipeUpdate
    list_filter = ['update']

class SiteAdmin(admin.ModelAdmin):
    fields = ('id', 'name', 'domain')
    readonly_fields = ('id',)
    list_display = ('id', 'name', 'domain')
    list_display_links = ('name',)
    search_fields = ('name', 'domain')

admin.site.unregister(Site)
admin.site.register(Site, SiteAdmin)
admin.site.register(Branch, BranchAdmin)
admin.site.register(YPCompatibleVersion, YPCompatibleVersionAdmin)
admin.site.register(LayerItem, LayerItemAdmin)
admin.site.register(LayerBranch, LayerBranchAdmin)
admin.site.register(LayerMaintainer, LayerMaintainerAdmin)
admin.site.register(LayerDependency, LayerDependencyAdmin)
admin.site.register(LayerNote, LayerNoteAdmin)
admin.site.register(Update, UpdateAdmin)
admin.site.register(LayerUpdate, LayerUpdateAdmin)
admin.site.register(PackageConfig, PackageConfigAdmin)
admin.site.register(StaticBuildDep, StaticBuildDepAdmin)
admin.site.register(DynamicBuildDep, DynamicBuildDepAdmin)
admin.site.register(Source, SourceAdmin)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(RecipeFileDependency)
admin.site.register(Machine, MachineAdmin)
admin.site.register(Distro, DistroAdmin)
admin.site.register(BBAppend, BBAppendAdmin)
admin.site.register(BBClass, BBClassAdmin)
admin.site.register(IncFile, IncFileAdmin)
admin.site.register(Patch, PatchAdmin)
admin.site.register(PatchDisposition, PatchDispositionAdmin)
admin.site.register(LayerRecipeExtraURL)
admin.site.register(RecipeChangeset, RecipeChangesetAdmin)
admin.site.register(ClassicRecipe, ClassicRecipeAdmin)
admin.site.register(ComparisonRecipeUpdate, ComparisonRecipeUpdateAdmin)
admin.site.register(PythonEnvironment)
admin.site.register(SiteNotice)
admin.site.register(SecurityQuestion)
admin.site.register(SecurityQuestionAnswer)
admin.site.register(UserProfile)
