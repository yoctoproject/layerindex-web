# layerindex-web - URL definitions
#
# Copyright (C) 2013, 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.views.generic import TemplateView, DetailView, ListView, RedirectView
from django.views.defaults import page_not_found
from django.urls import include, re_path, reverse_lazy
from layerindex.views import LayerListView, LayerReviewListView, LayerReviewDetailView, RecipeSearchView, \
    MachineSearchView, LayerDetailView, edit_layer_view, delete_layer_view, edit_layernote_view, delete_layernote_view, \
    HistoryListView, EditProfileFormView, AdvancedRecipeSearchView, BulkChangeView, BulkChangeSearchView, \
    bulk_change_edit_view, bulk_change_patch_view, BulkChangeDeleteView, RecipeDetailView, RedirectParamsView, \
    ClassicRecipeSearchView, ClassicRecipeDetailView, ClassicRecipeStatsView, LayerUpdateDetailView, UpdateListView, \
    UpdateDetailView, StatsView, publish_view, LayerCheckListView, BBClassCheckListView, TaskStatusView, \
    ComparisonRecipeSelectView, ComparisonRecipeSelectDetailView, task_log_view, task_stop_view, email_test_view, \
    BranchCompareView, RecipeDependenciesView, update_layer_view
from layerindex.models import LayerItem, Recipe, RecipeChangeset
from rest_framework import routers
from . import restviews

router = routers.DefaultRouter()
router.register(r'branches', restviews.BranchViewSet)
router.register(r'layerItems', restviews.LayerItemViewSet)
router.register(r'layerBranches', restviews.LayerBranchViewSet)
router.register(r'layerDependencies', restviews.LayerDependencyViewSet)
router.register(r'layerMaintainers', restviews.LayerMaintainerViewSet)
router.register(r'layerNotes', restviews.LayerNoteViewSet)
router.register(r'recipes', restviews.RecipeViewSet)
router.register(r'recipesExtended', restviews.RecipeExtendedViewSet, 'recipesExtended')
router.register(r'machines', restviews.MachineViewSet)
router.register(r'distros', restviews.DistroViewSet)
router.register(r'classes', restviews.ClassViewSet)
router.register(r'layers', restviews.LayerViewSet, 'layers')
router.register(r'appends', restviews.AppendViewSet)
router.register(r'incFiles', restviews.IncFileViewSet)

urlpatterns = [
    re_path(r'^$',
        RedirectView.as_view(url=reverse_lazy('layer_list', args=('master',)), permanent=False),
        name='frontpage'),

    re_path(r'^api/', include(router.urls)),

    re_path(r'^layers/$',
        RedirectView.as_view(url=reverse_lazy('layer_list', args=('master',)), permanent=False)),
    re_path(r'^layer/(?P<slug>[-\w]+)/$',
        RedirectParamsView.as_view(permanent=False), {'redirect_name': 'layer_item', 'branch': 'master'}),
    re_path(r'^recipes/$',
        RedirectView.as_view(url=reverse_lazy('recipe_search', args=('master',)), permanent=False)),
    re_path(r'^machines/$',
        RedirectView.as_view(url=reverse_lazy('machine_search', args=('master',)), permanent=False)),
    re_path(r'^distros/$',
        RedirectView.as_view(url=reverse_lazy('distro_search', args=('master',)), permanent=False)),
    re_path(r'^classes/$',
        RedirectView.as_view(url=reverse_lazy('class_search', args=('master',)), permanent=False)),
    re_path(r'^submit/$', edit_layer_view, {'template_name': 'layerindex/submitlayer.html'}, name="submit_layer"),
    re_path(r'^submit/thanks/$',
        TemplateView.as_view(
            template_name='layerindex/submitthanks.html'),
        name="submit_layer_thanks"),
    re_path(r'^review/$',
        LayerReviewListView.as_view(
            template_name='layerindex/reviewlist.html'),
        name='layer_list_review'),
    re_path(r'^review/(?P<slug>[-\w]+)/$',
        LayerReviewDetailView.as_view(
            template_name='layerindex/reviewdetail.html'),
        name='layer_review'),
    re_path(r'^layer/(?P<slug>[-\w]+)/addnote/$',
        edit_layernote_view, {'template_name': 'layerindex/editlayernote.html'}, name="add_layernote"),
    re_path(r'^layer/(?P<slug>[-\w]+)/editnote/(?P<pk>[-\w]+)/$',
        edit_layernote_view, {'template_name': 'layerindex/editlayernote.html'}, name="edit_layernote"),
    re_path(r'^layer/(?P<slug>[-\w]+)/deletenote/(?P<pk>[-\w]+)/$',
        delete_layernote_view, {'template_name': 'layerindex/deleteconfirm.html'}, name="delete_layernote"),
    re_path(r'^layer/(?P<slug>[-\w]+)/delete/$',
        delete_layer_view, {'template_name': 'layerindex/deleteconfirm.html'}, name="delete_layer"),
    re_path(r'^recipe/(?P<pk>[-\w]+)/$',
        RecipeDetailView.as_view(
            template_name='layerindex/recipedetail.html'),
        name='recipe'),
    re_path(r'^layer/(?P<name>[-\w]+)/publish/$', publish_view, name="publish"),
    re_path(r'^layerupdate/(?P<pk>[-\w]+)/$',
        LayerUpdateDetailView.as_view(
            template_name='layerindex/layerupdate.html'),
        name='layerupdate'),
    re_path(r'^bulkchange/$',
        BulkChangeView.as_view(
            template_name='layerindex/bulkchange.html'),
        name="bulk_change"),
    re_path(r'^bulkchange/(?P<pk>\d+)/search/$',
        BulkChangeSearchView.as_view(
            template_name='layerindex/bulkchangesearch.html'),
        name="bulk_change_search"),
    re_path(r'^bulkchange/(?P<pk>\d+)/edit/$',
        bulk_change_edit_view, {'template_name': 'layerindex/bulkchangeedit.html'}, name="bulk_change_edit"),
    re_path(r'^bulkchange/(?P<pk>\d+)/review/$',
        DetailView.as_view(
            model=RecipeChangeset,
            context_object_name='changeset',
            template_name='layerindex/bulkchangereview.html'),
        name="bulk_change_review"),
    re_path(r'^bulkchange/(?P<pk>\d+)/patches/$',
        bulk_change_patch_view, name="bulk_change_patches"),
    re_path(r'^bulkchange/(?P<pk>\d+)/delete/$',
        BulkChangeDeleteView.as_view(
            template_name='layerindex/deleteconfirm.html'),
        name="bulk_change_delete"),
    re_path(r'^branch/(?P<branch>[-.\w]+)/',
        include('layerindex.urls_branch')),
    re_path(r'^updates/$',
        UpdateListView.as_view(
            template_name='layerindex/updatelist.html'),
        name='update_list'),
    re_path(r'^updates/(?P<pk>[-\w]+)/$',
        UpdateDetailView.as_view(
            template_name='layerindex/updatedetail.html'),
        name='update'),
    re_path(r'^history/$',
        HistoryListView.as_view(
            template_name='layerindex/history.html'),
        name='history_list'),
    re_path(r'^profile/$',
        EditProfileFormView.as_view(
            template_name='layerindex/profile.html'),
        name="profile"),
    re_path(r'^about/$',
        TemplateView.as_view(
            template_name='layerindex/about.html'),
        name="about"),
    re_path(r'^stats/$',
        StatsView.as_view(
            template_name='layerindex/stats.html'),
        name='stats'),
    re_path(r'^oe-classic/$',
        RedirectView.as_view(url=reverse_lazy('classic_recipe_search'), permanent=False),
        name='classic'),
    re_path(r'^oe-classic/recipes/$',
        RedirectView.as_view(url=reverse_lazy('comparison_recipe_search', kwargs={'branch': 'oe-classic'}), permanent=False),
        name='classic_recipe_search'),
    re_path(r'^oe-classic/stats/$',
        RedirectView.as_view(url=reverse_lazy('comparison_recipe_stats', kwargs={'branch': 'oe-classic'}), permanent=False),
        name='classic_recipe_stats'),
    re_path(r'^oe-classic/recipe/(?P<pk>[-\w]+)/$',
        ClassicRecipeDetailView.as_view(
            template_name='layerindex/classicrecipedetail.html'),
        name='classic_recipe'),
    re_path(r'^comparison/recipes/(?P<branch>[-.\w]+)/$',
        ClassicRecipeSearchView.as_view(
            template_name='layerindex/classicrecipes.html'),
        name='comparison_recipe_search'),
    re_path(r'^comparison/search-csv/(?P<branch>[-.\w]+)/$',
        ClassicRecipeSearchView.as_view(
            template_name='layerindex/classicrecipes_csv.txt',
            paginate_by=0,
            content_type='text/csv; charset=utf-8'),
        name='comparison_recipe_search_csv'),
    re_path(r'^comparison/stats/(?P<branch>[-.\w]+)/$',
        ClassicRecipeStatsView.as_view(
            template_name='layerindex/classicstats.html'),
        name='comparison_recipe_stats'),
    re_path(r'^comparison/recipe/(?P<pk>[-\w]+)/$',
        ClassicRecipeDetailView.as_view(
            template_name='layerindex/classicrecipedetail.html'),
        name='comparison_recipe'),
    re_path(r'^comparison/select/(?P<pk>[-\w]+)/$',
        ComparisonRecipeSelectView.as_view(
            template_name='layerindex/comparisonrecipeselect.html'),
        name='comparison_select'),
    re_path(r'^comparison/selectdetail/(?P<selectfor>[-\w]+)/(?P<pk>[-\w]+)/$',
        ComparisonRecipeSelectDetailView.as_view(
            template_name='layerindex/comparisonrecipeselectdetail.html'),
        name='comparison_select_detail'),
    re_path(r'^email_test/$',
        email_test_view,
        name='email_test'),
    re_path(r'^task/(?P<task_id>[-\w]+)/$',
        TaskStatusView.as_view(
            template_name='layerindex/task.html'),
        name='task_status'),
    re_path(r'^tasklog/(?P<task_id>[-\w]+)/$',
        task_log_view,
        name='task_log'),
    re_path(r'^stoptask/(?P<task_id>[-\w]+)/$',
        task_stop_view,
        name='task_stop'),
    re_path(r'^branch_comparison/$',
        BranchCompareView.as_view(
            template_name='layerindex/branchcompare.html'),
        name='branch_comparison'),
    re_path(r'^branch_comparison_plain/$',
        BranchCompareView.as_view(
            content_type='text/plain; charset=utf-8',
            template_name='layerindex/branchcompare_plain.txt'),
        name='branch_comparison_plain'),
    re_path(r'^recipe_deps/$',
        RecipeDependenciesView.as_view(
            template_name='layerindex/recipedeps.html'),
        name='recipe_deps'),
    re_path(r'^ajax/layerchecklist/(?P<branch>[-.\w]+)/$',
        LayerCheckListView.as_view(
            template_name='layerindex/layerchecklist.html'),
        name='layer_checklist'),
    re_path(r'^ajax/classchecklist/(?P<branch>[-.\w]+)/$',
        BBClassCheckListView.as_view(
            template_name='layerindex/classchecklist.html'),
        name='class_checklist'),
    re_path(r'.*', page_not_found, kwargs={'exception': Exception("Page not Found")})
]
