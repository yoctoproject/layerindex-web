# layerindex-web - URL definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.conf.urls.defaults import *
from django.views.generic import DetailView, ListView
from layerindex.models import LayerItem, Recipe
from layerindex.views import LayerListView, RecipeSearchView, PlainTextListView

urlpatterns = patterns('',
    url(r'^$',
        LayerListView.as_view(
            template_name='layerindex/index.html'),
            name='layer_list'),
    url(r'^submit/$', 'layerindex.views.submit_layer', name="submit_layer"),
    url(r'^submit/thanks$', 'layerindex.views.submit_layer_thanks', name="submit_layer_thanks"),
    url(r'^recipes/$',
        RecipeSearchView.as_view(
            template_name='layerindex/recipes.html'),
            name='recipe_search'),
    url(r'^review/$',
        ListView.as_view(
            queryset=LayerItem.objects.order_by('name').filter(status__in='N'),
            context_object_name='layer_list',
            template_name='layerindex/index.html'),
            name='layer_list_review'),
    url(r'^layer/(?P<slug>[-\w]+)/$',
        DetailView.as_view(
            model=LayerItem,
            slug_field = 'name',
            template_name='layerindex/detail.html'),
            name='layer_item'),
    url(r'^recipe/(?P<pk>[-\w]+)/$',
        DetailView.as_view(
            model=Recipe,
            template_name='layerindex/recipedetail.html'),
            name='recipe'),
    url(r'^layer/(?P<name>[-\w]+)/publish/$', 'layerindex.views.publish', name="publish"),
    url(r'^raw/recipes.txt$',
        PlainTextListView.as_view(
            queryset=Recipe.objects.order_by('pn', 'layer'),
            context_object_name='recipe_list',
            template_name='layerindex/rawrecipes.txt'),
            name='recipe_list_raw'),
    url(r'^about$', 'layerindex.views.about', name="about"),
    url(r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': 'layerindex/static/img/favicon.ico'}),
)
