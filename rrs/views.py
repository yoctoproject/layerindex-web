import urllib

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.core.urlresolvers import resolve

from layerindex.models import Recipe
from rrs.models import Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeUpstreamHistory, RecipeUpstream, \
        RecipeDistro, RecipeUpgrade

def _check_url_params(upstream_status, maintainer_name):
    get_object_or_404(Maintainer, name=maintainer_name)

    found = 0
    for us in RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT.keys():
        if RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[us] == upstream_status:
            found = 1
            break

    if found == 0:
        raise Http404

def _get_layer_branch_url(branch, layer_name):
    return ("http://layers.openembedded.org/layerindex/branch/%s/layer/%s/"\
                % (branch, layer_name))

class RecipeList():
    pk = None
    name = None
    version = None
    summary = None
    upstream_status = None
    upstream_version = None
    maintainer_name = None

    def __init__(self, pk, name, version, summary, upstream_status,
            upstream_version, maintainer_name):
        self.pk = pk
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

        self.recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
            milestone.end_date)

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

                maintainer = RecipeMaintainer.get_maintainer_by_recipe_and_history(
                        recipe, self.recipe_maintainer_history)
                if self.maintainer_name != 'All' and self.maintainer_name != maintainer.name:
                    continue

                recipe_list_item = RecipeList(recipe.id, recipe.pn, recipe.pv, recipe.summary,
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
        for rm in RecipeMaintainer.objects.filter(history =
                self.recipe_maintainer_history).values(
                'maintainer__name').distinct().order_by('maintainer__name'):
            all_maintainers.append(rm['maintainer__name'])
        context['all_maintainers'] = all_maintainers

        extra_url_param = '?' + urllib.urlencode({
            'upstream_status': self.upstream_status,
            'maintainer_name': self.maintainer_name.encode('utf8')
        })
        context['extra_url_param'] = extra_url_param

        return context

class RecipeUpgradeDetail():
    title = None
    version = None
    milestone_name = None
    date = None
    maintainer_name = None
    is_recipe_maintainer = None
    commit = None
    commit_url = None

    def __init__(self, title, version, milestone_name, date, 
            maintainer_name, is_recipe_maintainer, commit, commit_url):
        self.title = title
        self.version = version
        self.milestone_name = milestone_name
        self.date = date
        self.maintainer_name = maintainer_name
        self.is_recipe_maintainer = is_recipe_maintainer
        self.commit = commit
        self.commit_url = commit_url

def _get_recipe_upgrade_detail(recipe_upgrade):
    milestone = Milestone.get_by_date(recipe_upgrade.commit_date)
    if milestone is None:
        milestone_name = ''
        recipe_maintainer_history = None
    else:
        milestone_name = milestone.name
        recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
            milestone.end_date)

    is_recipe_maintainer = False
    maintainer_name = ''
    if not recipe_upgrade.maintainer is None:
        maintainer_name = recipe_upgrade.maintainer.name

        if not recipe_maintainer_history is None and \
            RecipeMaintainer.objects.filter(maintainer__name
            = maintainer_name, history = recipe_maintainer_history) \
            .count() > 0:
            is_recipe_maintainer = True

    commit = recipe_upgrade.sha1[:10]
    commit_url = recipe_upgrade.recipe.layerbranch.layer.vcs_web_url + \
        '/commit/?id=' + recipe_upgrade.sha1

    rud = RecipeUpgradeDetail(recipe_upgrade.title, recipe_upgrade.version, \
            milestone_name, recipe_upgrade.commit_date, maintainer_name, \
            is_recipe_maintainer, commit, commit_url)

    return rud

class RecipeDetailView(DetailView):
    model = Recipe

    def get_context_data(self, **kwargs):
        context = super(RecipeDetailView, self).get_context_data(**kwargs)
        recipe = self.get_object()

        milestone = Milestone.get_current()
        context['milestone_name'] = milestone.name

        recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
            milestone.start_date,
            milestone.end_date
        )
        recipe_upstream = RecipeUpstream.get_by_recipe_and_history(
            recipe, recipe_upstream_history)
        context['upstream_status'] = \
            RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[recipe_upstream.status]
        context['upstream_version'] = recipe_upstream.version
        context['upstream_no_update_reason'] = recipe_upstream.no_update_reason

        self.recipe_maintainer_history = RecipeMaintainerHistory.get_last()
        recipe_maintainer = RecipeMaintainer.objects.filter(recipe = recipe,
                history = self.recipe_maintainer_history)[0]
        maintainer = recipe_maintainer.maintainer

        context['maintainer_name'] = maintainer.name

        context['recipe_upgrade_details'] = []
        for ru in RecipeUpgrade.objects.filter(recipe =
                recipe).order_by('-commit_date'): 
            context['recipe_upgrade_details'].append(_get_recipe_upgrade_detail(ru))
        context['recipe_upgrade_detail_count'] = len(context['recipe_upgrade_details'])

        context['recipe_layer_branch_url'] = _get_layer_branch_url(
                recipe.layerbranch.branch.name, recipe.layerbranch.layer.name)

        context['recipe_provides'] = []
        for p in recipe.provides.split():
            context['recipe_provides'].append(p)

        context['recipe_depends'] = []
        for d in recipe.depends.split():
            context['recipe_depends'].append(d)

        context['recipe_distros'] = RecipeDistro.get_distros_by_recipe(recipe)

        return context
