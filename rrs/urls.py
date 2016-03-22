from django.views.generic import TemplateView
from django.conf.urls import patterns, url

from layerindex.views import EditProfileFormView

from rrs.models import Release, Milestone
from rrs.views import RecipeListView, recipes_report, RecipeDetailView, \
    MaintainerListView, FrontPageRedirect

urlpatterns = patterns('',
    url(r'^$', FrontPageRedirect.as_view(),
        name='frontpage'),
    url(r'^recipes/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        RecipeListView.as_view(
            template_name='rrs/recipes.html'),
        name='recipes'),
    url(r'^recipesreport/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        recipes_report,
        name="recipesreport"),
    url(r'^recipedetail/(?P<pk>\d+)/$',
        RecipeDetailView.as_view(
            template_name='rrs/recipedetail.html'),
        name='recipedetail'),
    url(r'^maintainers/(?P<release_name>.*)/(?P<milestone_name>.*)/$',
        MaintainerListView.as_view(
        template_name='rrs/maintainers.html'),
        name="maintainers"),
    url(r'^profile/$',
        EditProfileFormView.as_view(
        template_name='layerindex/profile.html'),
        name="profile"),
    url(r'^about/$',
        TemplateView.as_view(
        template_name='rrs/about.html'),
        name="about"),
)
