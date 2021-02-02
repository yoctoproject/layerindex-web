# rrs-web - URLS
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.conf.urls import include, url

from rrs.models import Release, Milestone
from rrs.views import RecipeListView, recipes_report, RecipeDetailView, \
    MaintainerListView, FrontPageRedirect, MaintenancePlanRedirect, \
    MaintenanceStatsView

urlpatterns = [
    url(r'^$', FrontPageRedirect.as_view(),
        name='rrs_frontpage'),
    url(r'^maintplan/(?P<maintplan_name>.*)/$',
        MaintenancePlanRedirect.as_view(),
        name='rrs_maintplan'),
    url(r'^recipes/(?P<maintplan_name>.*)/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        RecipeListView.as_view(
            template_name='rrs/recipes.html'),
        name='rrs_recipes'),
    url(r'^recipesreport/(?P<maintplan_name>.*)/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        recipes_report,
        name="rrs_recipesreport"),
    url(r'^recipedetail/(?P<maintplan_name>.*)/(?P<pk>\d+)/$',
        RecipeDetailView.as_view(
            template_name='rrs/recipedetail.html'),
        name='rrs_recipedetail'),
    url(r'^maintainers/(?P<maintplan_name>.*)/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        MaintainerListView.as_view(
        template_name='rrs/maintainers.html'),
        name="rrs_maintainers"),
    url(r'^stats/(?P<maintplan_name>.*)/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        MaintenanceStatsView.as_view(
        template_name='rrs/rrs_stats.html'),
        name="rrs_stats"),
]
