from django.conf.urls import patterns, include, url

from rrs.models import Milestone
from rrs.views import RecipeListView, RecipeDetailView, MaintainerListView

urlpatterns = patterns('',
    url(r'^$', redirect_to, {'url' : reverse_lazy('recipes', args=(Milestone.get_current().name,))},
        name='frontpage'),
    url(r'^recipes/(?P<milestone_name>.*)/$',
        RecipeListView.as_view(
            template_name='rrs/recipes.html'),
        name='recipes'),
    url(r'^recipedetail/(?P<pk>\d+)/$',
        RecipeDetailView.as_view(
            template_name='rrs/recipedetail.html'),
        name='recipedetail'),
    url(r'^maintainers/(?P<milestone_name>.*)/$',
        MaintainerListView.as_view(
        template_name='rrs/maintainers.html'),
        name="maintainers"),
)
