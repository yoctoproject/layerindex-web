# layerindex-web - Branch-based URL definitions
#
# Copyright (C) 2013-2016 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.views.defaults import page_not_found
from django.urls import include, re_path, reverse_lazy
from layerindex.views import LayerListView, RecipeSearchView, MachineSearchView, DistroSearchView, ClassSearchView, LayerDetailView, edit_layer_view, delete_layer_view, edit_layernote_view, delete_layernote_view, RedirectParamsView, DuplicatesView, LayerUpdateDetailView, layer_export_recipes_csv_view, comparison_update_view, update_layer_view

urlpatterns = [
    re_path(r'^$',
        RedirectParamsView.as_view(permanent=False), {'redirect_name': 'layer_list'}),
    re_path(r'^layers/$',
        LayerListView.as_view(
            template_name='layerindex/layers.html'),
            name='layer_list'),
    re_path(r'^layer/(?P<slug>[-\.\w]+)/$',
        LayerDetailView.as_view(
            template_name='layerindex/detail.html'),
            name='layer_item'),
    re_path(r'^layer/(?P<slug>[-\.\w]+)/recipes/csv/$',
        layer_export_recipes_csv_view,
        name='layer_export_recipes_csv'),
    re_path(r'^recipes/$',
        RecipeSearchView.as_view(
            template_name='layerindex/recipes.html'),
            name='recipe_search'),
    re_path(r'^machines/$',
        MachineSearchView.as_view(
            template_name='layerindex/machines.html'),
            name='machine_search'),
    re_path(r'^distros/$',
        DistroSearchView.as_view(
            template_name='layerindex/distros.html'),
            name='distro_search'),
    re_path(r'^classes/$',
        ClassSearchView.as_view(
            template_name='layerindex/classes.html'),
            name='class_search'),
    re_path(r'^edit/(?P<slug>[-\.\w]+)/$', edit_layer_view, {'template_name': 'layerindex/editlayer.html'}, name="edit_layer"),
    re_path(r'^update/(?P<slug>[-\.\w]+)/$', update_layer_view, {'template_name': 'layerindex/updatelayer.html'}, name="update_layer"),
    re_path(r'^duplicates/$',
        DuplicatesView.as_view(
            template_name='layerindex/duplicates.html'),
            name='duplicates'),
    re_path(r'^comparison_update/$',
        comparison_update_view,
        name='comparison_update'),
]
