from django.conf.urls import patterns, include, url

from rrs.models import Release, Milestone
from rrs.views import RecipeListView, recipes_report, RecipeDetailView, MaintainerListView

urlpatterns = patterns('',
    url(r'^$', redirect_to,
        {'url' :
            reverse_lazy('recipes',
                args = (
                    Release.get_current().name,
                    Milestone.get_current(Release.get_current()).name,
                )
            )
        },
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
)
