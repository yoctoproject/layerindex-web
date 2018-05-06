# layerindex-web - Branch-based URL definitions
#
# Copyright (C) 2013-2016 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.conf.urls import *
from django.views.defaults import page_not_found
from django.core.urlresolvers import reverse_lazy
from layerindex.views import LayerListView, RecipeSearchView, MachineSearchView, DistroSearchView, ClassSearchView, LayerDetailView, edit_layer_view, delete_layer_view, edit_layernote_view, delete_layernote_view, RedirectParamsView, DuplicatesView, LayerUpdateDetailView

urlpatterns = [
    url(r'^$', 
        RedirectParamsView.as_view(permanent=False), {'redirect_name': 'layer_list'}),
    url(r'^layers/$',
        LayerListView.as_view(
            template_name='layerindex/layers.html'),
            name='layer_list'),
    url(r'^layer/(?P<slug>[-\w]+)/$',
        LayerDetailView.as_view(
            template_name='layerindex/detail.html'),
            name='layer_item'),
    url(r'^recipes/$',
        RecipeSearchView.as_view(
            template_name='layerindex/recipes.html'),
            name='recipe_search'),
    url(r'^machines/$',
        MachineSearchView.as_view(
            template_name='layerindex/machines.html'),
            name='machine_search'),
    url(r'^distros/$',
        DistroSearchView.as_view(
            template_name='layerindex/distros.html'),
            name='distro_search'),
    url(r'^classes/$',
        ClassSearchView.as_view(
            template_name='layerindex/classes.html'),
            name='class_search'),
    url(r'^edit/(?P<slug>[-\w]+)/$', edit_layer_view, {'template_name': 'layerindex/editlayer.html'}, name="edit_layer"),
    url(r'^duplicates/$',
        DuplicatesView.as_view(
            template_name='layerindex/duplicates.html'),
            name='duplicates'),
]
