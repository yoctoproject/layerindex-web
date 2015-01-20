from django.conf.urls import patterns, include, url

from rrs.models import Milestone
from rrs.views import RecipeListView

urlpatterns = patterns('',
    url(r'^$', redirect_to, {'url' : reverse_lazy('recipes', args=(Milestone.get_current().name,))},
        name='frontpage'),
    url(r'^recipes/(?P<milestone_name>.*)/$',
        RecipeListView.as_view(
            template_name='rrs/recipes.html'),
        name='recipes'),
)
