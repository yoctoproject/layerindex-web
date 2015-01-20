from django.views.generic import ListView
from django.core.urlresolvers import resolve

from rrs.models import Milestone

class RecipeListView(ListView):
    context_object_name = 'recipe_list'

    def get_queryset(self):
        pass

    def get_context_data(self, **kwargs):
        context = super(RecipeListView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name
        context['milestone_name'] = self.kwargs['milestone_name']
        context['all_milestones'] = Milestone.objects.filter().order_by('-id')

        return context
