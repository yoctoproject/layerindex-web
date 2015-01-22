import urllib

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.core.urlresolvers import resolve

from layerindex.models import Recipe
from rrs.models import Milestone, Maintainer, RecipeMaintainer, RecipeUpstream, \
        RecipeUpstreamHistory

def _check_url_params(upstream_status, maintainer_name):
    get_object_or_404(Maintainer, name=maintainer_name)

    found = 0
    for us in RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT.keys():
        if RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[us] == upstream_status:
            found = 1
            break

    if found == 0:
        raise Http404

class RecipeList():
    name = None
    version = None
    summary = None
    upstream_status = None
    upstream_version = None
    maintainer_name = None

    def __init__(self, name, version, summary, upstream_status,
            upstream_version, maintainer_name):
        self.name = name
        self.version = version
        self.summary = summary
        self.upstream_status = upstream_status
        self.upstream_version = upstream_version
        self.maintainer_name = maintainer_name

class RecipeListView(ListView):
    context_object_name = 'recipe_list'

    def get_queryset(self):
        self.milestone_name = self.kwargs['milestone_name']
        milestone = get_object_or_404(Milestone, name=self.milestone_name)

        if 'upstream_status' in self.request.GET.keys():
            self.upstream_status = self.request.GET['upstream_status']
        else:
            self.upstream_status = 'All'

        if 'maintainer_name' in self.request.GET.keys():
            self.maintainer_name = self.request.GET['maintainer_name']
        else:
            self.maintainer_name = 'All'

        _check_url_params(self.upstream_status, self.maintainer_name)

        recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
            milestone.start_date,
            milestone.end_date
        )

        recipe_list = []
        self.recipe_list_count = 0

        self.recipes_up_to_date = 0
        self.recipes_not_updated = 0
        self.recipes_unknown = 0
        self.recipes_percentage = '0.00'
        if not recipe_upstream_history is None:
            recipe_qry = Recipe.objects.filter().order_by('pn')

            # get statistics by milestone
            recipes_all = RecipeUpstream.objects.filter(history =
                    recipe_upstream_history).count()
            self.recipes_up_to_date = RecipeUpstream.objects.filter(history =
                    recipe_upstream_history, status = 'Y').count()
            self.recipes_not_updated = RecipeUpstream.objects.filter(history =
                    recipe_upstream_history, status = 'N').count()
            self.recipes_unknown = recipes_all - (self.recipes_up_to_date +
                    self.recipes_not_updated)
            self.recipes_percentage = "%.2f" % \
                ((float(self.recipes_up_to_date) / float(recipes_all)) * 100)

            for recipe in recipe_qry:
                recipe_upstream = RecipeUpstream.get_by_recipe_and_history(
                        recipe, recipe_upstream_history)

                recipe_upstream_status = \
                        RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[
                                recipe_upstream.status]
                if self.upstream_status != 'All' and self.upstream_status != recipe_upstream_status:
                    continue

                maintainer = RecipeMaintainer.get_maintainer_by_recipe(recipe)
                if self.maintainer_name != 'All' and self.maintainer_name != maintainer.name:
                    continue

                recipe_list_item = RecipeList(recipe.pn, recipe.pv, recipe.summary,
                        recipe_upstream_status, recipe_upstream.version, maintainer.name)
                recipe_list.append(recipe_list_item)

            self.recipe_list_count = len(recipe_list)

        return recipe_list

    def get_context_data(self, **kwargs):
        context = super(RecipeListView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name

        context['milestone_name'] = self.milestone_name
        context['all_milestones'] = Milestone.objects.filter().order_by('-id')

        context['recipes_percentage'] = self.recipes_percentage
        context['recipes_up_to_date'] = self.recipes_up_to_date
        context['recipes_not_updated'] = self.recipes_not_updated
        context['recipes_unknown'] = self.recipes_unknown

        context['recipe_list_count'] = self.recipe_list_count

        context['upstream_status'] = self.upstream_status
        all_upstream_status = []
        for us in RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES:
            all_upstream_status.append(us[1])
        context['all_upstream_status'] = all_upstream_status

        context['maintainer_name'] = self.maintainer_name
        all_maintainers = ['All']
        for rm in RecipeMaintainer.objects.filter().values(
                'maintainer__name').distinct().order_by('maintainer__name'):
            all_maintainers.append(rm['maintainer__name'])
        context['all_maintainers'] = all_maintainers

        extra_url_param = '?' + urllib.urlencode({
            'upstream_status': self.upstream_status,
            'maintainer_name': self.maintainer_name.encode('utf8')
        })
        context['extra_url_param'] = extra_url_param

        return context
