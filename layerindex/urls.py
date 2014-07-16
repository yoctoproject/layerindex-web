# layerindex-web - URL definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.conf.urls.defaults import *
from django.views.generic import TemplateView, DetailView, ListView
from django.views.generic.simple import redirect_to
from django.views.defaults import page_not_found
from django.core.urlresolvers import reverse_lazy
from layerindex.views import LayerListView, LayerReviewListView, LayerReviewDetailView, RecipeSearchView, MachineSearchView, PlainTextListView, LayerDetailView, edit_layer_view, delete_layer_view, edit_layernote_view, delete_layernote_view, HistoryListView, EditProfileFormView, AdvancedRecipeSearchView, BulkChangeView, BulkChangeSearchView, bulk_change_edit_view, bulk_change_patch_view, BulkChangeDeleteView, RecipeDetailView, RedirectParamsView, ClassicRecipeSearchView, ClassicRecipeDetailView, ClassicRecipeStatsView
from layerindex.models import LayerItem, Recipe, RecipeChangeset
from rest_framework import routers
import restviews
from django.conf.urls import include

router = routers.DefaultRouter()
router.register(r'branches', restviews.BranchViewSet)
router.register(r'layerItems', restviews.LayerItemViewSet)
router.register(r'layerBranches', restviews.LayerBranchViewSet)
router.register(r'layerDependencies', restviews.LayerDependencyViewSet)
router.register(r'recipes', restviews.RecipeViewSet)
router.register(r'machines', restviews.MachineViewSet)

urlpatterns = patterns('',
    url(r'^$', redirect_to, {'url' : reverse_lazy('layer_list', args=('master',))},
        name='frontpage'),

    url(r'^api/', include(router.urls)),

    url(r'^layers/$',
        redirect_to, {'url' : reverse_lazy('layer_list', args=('master',))}),
    url(r'^layer/(?P<slug>[-\w]+)/$',
        RedirectParamsView.as_view(), {'redirect_name': 'layer_item', 'branch':'master'}),
    url(r'^recipes/$',
        redirect_to, {'url' : reverse_lazy('recipe_search', args=('master',))}),
    url(r'^machines/$',
        redirect_to, {'url' : reverse_lazy('machine_search', args=('master',))}),
 
    url(r'^submit/$', edit_layer_view, {'template_name': 'layerindex/submitlayer.html'}, name="submit_layer"),
    url(r'^submit/thanks$',
        TemplateView.as_view(
            template_name='layerindex/submitthanks.html'),
            name="submit_layer_thanks"),
    url(r'^review/$',
        LayerReviewListView.as_view(
            template_name='layerindex/reviewlist.html'),
            name='layer_list_review'),
    url(r'^review/(?P<slug>[-\w]+)/$',
        LayerReviewDetailView.as_view(
            template_name='layerindex/reviewdetail.html'),
            name='layer_review'),
    url(r'^layer/(?P<slug>[-\w]+)/addnote/$',
        edit_layernote_view, {'template_name': 'layerindex/editlayernote.html'}, name="add_layernote"),
    url(r'^layer/(?P<slug>[-\w]+)/editnote/(?P<pk>[-\w]+)/$',
        edit_layernote_view, {'template_name': 'layerindex/editlayernote.html'}, name="edit_layernote"),
    url(r'^layer/(?P<slug>[-\w]+)/deletenote/(?P<pk>[-\w]+)/$',
        delete_layernote_view, {'template_name': 'layerindex/deleteconfirm.html'}, name="delete_layernote"),
    url(r'^layer/(?P<slug>[-\w]+)/delete/$',
        delete_layer_view, {'template_name': 'layerindex/deleteconfirm.html'}, name="delete_layer"),
    url(r'^recipe/(?P<pk>[-\w]+)/$',
        RecipeDetailView.as_view(
            template_name='layerindex/recipedetail.html'),
            name='recipe'),
    url(r'^layer/(?P<name>[-\w]+)/publish/$', 'layerindex.views.publish', name="publish"),
    url(r'^bulkchange/$',
        BulkChangeView.as_view(
            template_name='layerindex/bulkchange.html'),
            name="bulk_change"),
    url(r'^bulkchange/(?P<pk>\d+)/search/$',
        BulkChangeSearchView.as_view(
            template_name='layerindex/bulkchangesearch.html'),
            name="bulk_change_search"),
    url(r'^bulkchange/(?P<pk>\d+)/edit/$',
        bulk_change_edit_view, {'template_name': 'layerindex/bulkchangeedit.html'}, name="bulk_change_edit"),
    url(r'^bulkchange/(?P<pk>\d+)/review/$',
        DetailView.as_view(
            model=RecipeChangeset,
            context_object_name='changeset',
            template_name='layerindex/bulkchangereview.html'),
            name="bulk_change_review"),
    url(r'^bulkchange/(?P<pk>\d+)/patches/$',
        bulk_change_patch_view, name="bulk_change_patches"),
    url(r'^bulkchange/(?P<pk>\d+)/delete/$',
        BulkChangeDeleteView.as_view(
            template_name='layerindex/deleteconfirm.html'),
            name="bulk_change_delete"),
    url(r'^branch/(?P<branch>[-\w]+)/',
        include('layerindex.urls_branch')),
    #url(r'^raw/recipes.txt$',
    #    PlainTextListView.as_view(
    #        queryset=Recipe.objects.order_by('pn', 'layerbranch__layer'),
    #        context_object_name='recipe_list',
    #        template_name='layerindex/rawrecipes.txt'),
    #        name='recipe_list_raw'),
    url(r'^history/$',
        HistoryListView.as_view(
            template_name='layerindex/history.html'),
            name='history_list'),
    url(r'^profile/$',
        EditProfileFormView.as_view(
            template_name='layerindex/profile.html'),
            name="profile"),
    url(r'^about$',
        TemplateView.as_view(
            template_name='layerindex/about.html'),
            name="about"),
    url(r'^oe-classic/$',
        redirect_to, {'url' : reverse_lazy('classic_recipe_search')},
            name='classic'),
    url(r'^oe-classic/recipes/$',
        ClassicRecipeSearchView.as_view(
            template_name='layerindex/classicrecipes.html'),
            name='classic_recipe_search'),
    url(r'^oe-classic/stats/$',
        ClassicRecipeStatsView.as_view(
            template_name='layerindex/classicstats.html'),
            name='classic_recipe_stats'),
    url(r'^oe-classic/recipe/(?P<pk>[-\w]+)/$',
        ClassicRecipeDetailView.as_view(
            template_name='layerindex/classicrecipedetail.html'),
            name='classic_recipe'),
    url(r'.*', page_not_found)
)
