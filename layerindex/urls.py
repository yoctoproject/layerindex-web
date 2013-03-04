# layerindex-web - URL definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.conf.urls.defaults import *
from django.views.generic import DetailView, ListView
from layerindex.models import LayerItem, Recipe
from layerindex.views import LayerListView, LayerReviewListView, RecipeSearchView, MachineSearchView, PlainTextListView, LayerDetailView, edit_layer_view, delete_layer_view, edit_layernote_view, delete_layernote_view, switch_branch_view

urlpatterns = patterns('',
    url(r'^$',
        LayerListView.as_view(
            template_name='layerindex/index.html'),
            name='layer_list'),
    url(r'^submit/$', edit_layer_view, {'template_name': 'layerindex/submitlayer.html'}, name="submit_layer"),
    url(r'^edit/(?P<slug>[-\w]+)/$', edit_layer_view, {'template_name': 'layerindex/editlayer.html'}, name="edit_layer"),
    url(r'^submit/thanks$', 'layerindex.views.submit_layer_thanks', name="submit_layer_thanks"),
    url(r'^recipes/$',
        RecipeSearchView.as_view(
            template_name='layerindex/recipes.html'),
            name='recipe_search'),
    url(r'^machines/$',
        MachineSearchView.as_view(
            template_name='layerindex/machines.html'),
            name='machine_search'),
    url(r'^review/$',
        LayerReviewListView.as_view(
            template_name='layerindex/index.html'),
            name='layer_list_review'),
    url(r'^layer/(?P<slug>[-\w]+)/$',
        LayerDetailView.as_view(
            template_name='layerindex/detail.html'),
            name='layer_item'),
    url(r'^layer/(?P<slug>[-\w]+)/addnote/$',
        edit_layernote_view, {'template_name': 'layerindex/editlayernote.html'}, name="add_layernote"),
    url(r'^layer/(?P<slug>[-\w]+)/editnote/(?P<pk>[-\w]+)/$',
        edit_layernote_view, {'template_name': 'layerindex/editlayernote.html'}, name="edit_layernote"),
    url(r'^layer/(?P<slug>[-\w]+)/deletenote/(?P<pk>[-\w]+)/$',
        delete_layernote_view, {'template_name': 'layerindex/deleteconfirm.html'}, name="delete_layernote"),
    url(r'^layer/(?P<slug>[-\w]+)/delete/$',
        delete_layer_view, {'template_name': 'layerindex/deleteconfirm.html'}, name="delete_layer"),
    url(r'^recipe/(?P<pk>[-\w]+)/$',
        DetailView.as_view(
            model=Recipe,
            template_name='layerindex/recipedetail.html'),
            name='recipe'),
    url(r'^layer/(?P<name>[-\w]+)/publish/$', 'layerindex.views.publish', name="publish"),
    url(r'^branch/(?P<slug>[-\w]+)/$',
        switch_branch_view, name="switch_branch"),
    url(r'^raw/recipes.txt$',
        PlainTextListView.as_view(
            queryset=Recipe.objects.order_by('pn', 'layer'),
            context_object_name='recipe_list',
            template_name='layerindex/rawrecipes.txt'),
            name='recipe_list_raw'),
    url(r'^about$', 'layerindex.views.about', name="about"),
)
