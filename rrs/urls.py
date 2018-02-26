from django.conf.urls import patterns, include, url

from rrs.models import Release, Milestone
from rrs.views import RecipeListView, recipes_report, RecipeDetailView, \
    MaintainerListView, FrontPageRedirect

urlpatterns = patterns('',
    url(r'^$', FrontPageRedirect.as_view(),
        name='rrs_frontpage'),
    url(r'^recipes/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        RecipeListView.as_view(
            template_name='rrs/recipes.html'),
        name='rrs_recipes'),
    url(r'^recipesreport/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        recipes_report,
        name="rrs_recipesreport"),
    url(r'^recipedetail/(?P<pk>\d+)/$',
        RecipeDetailView.as_view(
            template_name='rrs/recipedetail.html'),
        name='rrs_recipedetail'),
    url(r'^maintainers/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        MaintainerListView.as_view(
        template_name='rrs/maintainers.html'),
        name="rrs_maintainers"),
)
