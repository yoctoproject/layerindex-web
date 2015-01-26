from django.views.generic import TemplateView
from django.views.generic.simple import redirect_to
from django.core.urlresolvers import reverse_lazy

from django.conf.urls import patterns, url

from layerindex.views import EditProfileFormView

from rrs.models import Milestone
from rrs.views import RecipeListView, RecipeDetailView

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
    url(r'^profile/$',
        EditProfileFormView.as_view(
        template_name='layerindex/profile.html'),
        name="profile"),
    url(r'^about/$',
        TemplateView.as_view(
        template_name='rrs/about.html'),
        name="about"),
)
