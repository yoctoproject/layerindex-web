import urllib

import csv
from django.http import HttpResponse

from datetime import date
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.core.urlresolvers import resolve

from layerindex.models import Recipe
from rrs.models import Release, Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeUpstreamHistory, RecipeUpstream, \
        RecipeDistro, RecipeUpgrade

def _check_url_params(upstream_status, maintainer_name):
    get_object_or_404(Maintainer, name=maintainer_name)

    found = 0
    for us in RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT.keys():
        if us == 'D': # Downgrade is displayed as Unknown
            continue

        if RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[us] == upstream_status:
            found = 1
            break

    if found == 0:
        raise Http404

def _get_layer_branch_url(branch, layer_name):
    return ("http://layers.openembedded.org/layerindex/branch/%s/layer/%s/"\
                % (branch, layer_name))

def _get_milestone_statistics(milestone, maintainer_name=None):
    milestone_statistics = {}

    recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
        milestone.start_date,
        milestone.end_date
    )

    if maintainer_name is None:
        milestone_statistics['all'] = Recipe.objects.all().count()

        milestone_statistics['up_to_date'] = \
            RecipeUpstream.get_recipes_up_to_date(recipe_upstream_history).count()
        milestone_statistics['not_updated'] = \
            RecipeUpstream.get_recipes_not_updated(recipe_upstream_history).count()
        milestone_statistics['cant_be_updated'] = \
            RecipeUpstream.get_recipes_cant_be_updated(recipe_upstream_history).count()
        milestone_statistics['unknown'] = \
            RecipeUpstream.get_recipes_unknown(recipe_upstream_history).count()
    else:
        recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
            milestone.end_date)
        recipe_maintainer_all = RecipeMaintainer.objects.filter(history = recipe_maintainer_history,
            maintainer__name = maintainer_name)
        milestone_statistics['all'] = len(recipe_maintainer_all)

        recipe_upstream_all = []
        for rm in recipe_maintainer_all:
            ru_qry = RecipeUpstream.objects.filter(recipe = rm.recipe, history =
                        recipe_upstream_history)
            if ru_qry:
                recipe_upstream_all.append(ru_qry[0])

        milestone_statistics['up_to_date'] = 0
        milestone_statistics['not_updated'] = 0
        milestone_statistics['cant_be_updated'] = 0
        milestone_statistics['unknown'] = 0
        for ru in recipe_upstream_all:
            if ru.status == 'Y':
                milestone_statistics['up_to_date'] += 1
            elif ru.status == 'N':
                if ru.no_update_reason == '':
                    milestone_statistics['not_updated'] += 1
                else:
                    milestone_statistics['cant_be_updated'] += 1
            else:
                milestone_statistics['unknown'] += 1

    if milestone_statistics['all'] == 0:
        milestone_statistics['percentage'] = 0
    else:
        milestone_statistics['percentage'] = "%.0f" % \
            ((float(milestone_statistics['up_to_date']) /
                float(milestone_statistics['all'])) * 100)

    return milestone_statistics

class RecipeList():
    pk = None
    name = None
    version = None
    summary = None
    upstream_status = None
    upstream_version = None
    maintainer_name = None
    no_update_reason = None

    def __init__(self, pk, name, summary):
        self.pk = pk
        self.name = name
        self.summary = summary

def _get_recipe_list(milestone):
    recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
        milestone.end_date)

    recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
        milestone.start_date,
        milestone.end_date
    )

    recipe_list = []
    current_date = date.today()
    for recipe in Recipe.objects.filter().order_by('pn'):
        if current_date >= milestone.start_date and \
            current_date <= milestone.end_date:
            version = recipe.pv
        else:
            rup = RecipeUpgrade.get_by_recipe_and_date(recipe,
                    milestone.end_date)

            if rup is None: # Recipe don't exit in this Milestone
                continue

            version = rup.version

        upstream_version = ''
        upstream_status = ''
        no_update_reason = ''
        if recipe_upstream_history:
            recipe_upstream = RecipeUpstream.get_by_recipe_and_history(
                    recipe, recipe_upstream_history)

            if recipe_upstream is None:
                recipe_upstream = RecipeUpstream()
                recipe_upstream.history = recipe_upstream_history
                recipe_upstream.recipe = recipe
                recipe_upstream.version = ''
                recipe_upstream.type = 'M' # Manual
                recipe_upstream.status = 'U' # Unknown
                recipe_upstream.no_update_reason = ''
                recipe_upstream.date = recipe_upstream_history.end_date
                recipe_upstream.save()

            if recipe_upstream.status == 'N' and recipe_upstream.no_update_reason:
                recipe_upstream.status = 'C'
            upstream_status = \
                RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[
                         recipe_upstream.status]
            if upstream_status == 'Downgrade':
                upstream_status = 'Unknown' # Downgrade is displayed as Unknown
            upstream_version = recipe_upstream.version
            no_update_reason = recipe_upstream.no_update_reason

        maintainer = RecipeMaintainer.get_maintainer_by_recipe_and_history(
                recipe, recipe_maintainer_history)
        if maintainer is None:
            maintainer_name = ''
        else:
            maintainer_name = maintainer.name

        recipe_list_item = RecipeList(recipe.id, recipe.pn, recipe.summary)
        recipe_list_item.version = version
        recipe_list_item.upstream_status = upstream_status
        recipe_list_item.upstream_version = upstream_version
        recipe_list_item.maintainer_name = maintainer_name
        recipe_list_item.no_update_reason = no_update_reason
        recipe_list.append(recipe_list_item)

    return recipe_list

class RecipeListView(ListView):
    context_object_name = 'recipe_list'

    def get_queryset(self):
        self.release_name = self.kwargs['release_name']
        release = get_object_or_404(Release, name=self.release_name)

        self.milestone_name = self.kwargs['milestone_name']
        milestone = get_object_or_404(Milestone, release = release, name=self.milestone_name)

        if 'upstream_status' in self.request.GET.keys():
            self.upstream_status = self.request.GET['upstream_status']
        else:
            self.upstream_status = 'All'

        if 'maintainer_name' in self.request.GET.keys():
            self.maintainer_name = self.request.GET['maintainer_name']
        else:
            self.maintainer_name = 'All'

        _check_url_params(self.upstream_status, self.maintainer_name)

        self.milestone_statistics = _get_milestone_statistics(milestone)

        self.recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
            milestone.end_date)

        recipe_list = _get_recipe_list(milestone)
        self.recipe_list_count = len(recipe_list)

        return recipe_list

    def get_context_data(self, **kwargs):
        context = super(RecipeListView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name

        context['release_name'] = self.release_name
        context['all_releases'] = Release.objects.filter().order_by('-end_date')
        context['milestone_name'] = self.milestone_name
        context['all_milestones'] = Milestone.objects.filter(release__name =
                self.release_name).order_by('-end_date')

        context['recipes_percentage'] = self.milestone_statistics['percentage']
        context['recipes_up_to_date'] = self.milestone_statistics['up_to_date']
        context['recipes_not_updated'] = self.milestone_statistics['not_updated']
        context['recipes_cant_be_updated'] = self.milestone_statistics['cant_be_updated']
        context['recipes_unknown'] = self.milestone_statistics['unknown']

        context['recipe_list_count'] = self.recipe_list_count

        context['upstream_status'] = self.upstream_status
        ruch = RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT
        context['upstream_status_set_choices'] = [ruch['A']]
        context['upstream_status_choices'] = [ruch['N'], ruch['C'], ruch['Y'], ruch['U']]

        context['maintainer_name'] = self.maintainer_name
        context['set_maintainers'] =  ['All', 'No maintainer']
        all_maintainers = []
        for rm in RecipeMaintainer.objects.filter(history =
                self.recipe_maintainer_history).values(
                'maintainer__name').distinct().order_by('maintainer__name'):
            if rm['maintainer__name'] in context['set_maintainers']:
                continue
            all_maintainers.append(rm['maintainer__name'])
        context['all_maintainers'] = all_maintainers

        extra_url_param = '?' + urllib.urlencode({
            'upstream_status': self.upstream_status,
            'maintainer_name': self.maintainer_name.encode('utf8')
        })
        context['extra_url_param'] = extra_url_param

        return context

def recipes_report(request, release_name, milestone_name):
    release = get_object_or_404(Release, name=release_name)
    milestone = get_object_or_404(Milestone, release = release, name=milestone_name)

    recipe_list = _get_recipe_list(milestone)

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s.csv"' % (milestone_name)

    writer = csv.writer(response)
    writer.writerow(['Upstream status', 'Name', 'Version',
        'Upstream version', 'Maintainer', 'Summary'])
    for r in recipe_list:
        writer.writerow([r.upstream_status, r.name, r.version,
            r.upstream_version, r.maintainer_name.encode('utf-8'), r.summary])

    return response

class RecipeUpgradeDetail():
    title = None
    version = None
    release_name = None
    milestone_name = None
    date = None
    maintainer_name = None
    is_recipe_maintainer = None
    commit = None
    commit_url = None

    def __init__(self, title, version, release_name, milestone_name, date, 
            maintainer_name, is_recipe_maintainer, commit, commit_url):
        self.title = title
        self.version = version
        self.release_name = release_name
        self.milestone_name = milestone_name
        self.date = date
        self.maintainer_name = maintainer_name
        self.is_recipe_maintainer = is_recipe_maintainer
        self.commit = commit
        self.commit_url = commit_url

def _get_recipe_upgrade_detail(recipe_upgrade):
    release_name = ''
    milestone_name = ''
    recipe_maintainer_history = None

    release = Release.get_by_date(recipe_upgrade.commit_date)
    if release:
        release_name = release.name
        milestone = Milestone.get_by_release_and_date(release,
                recipe_upgrade.commit_date)
        if milestone:
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
            release_name, milestone_name, recipe_upgrade.commit_date, \
            maintainer_name, is_recipe_maintainer, commit, commit_url)

    return rud

class RecipeDetailView(DetailView):
    model = Recipe

    def get_context_data(self, **kwargs):
        context = super(RecipeDetailView, self).get_context_data(**kwargs)
        recipe = self.get_object()

        release = Release.get_current()
        context['release_name'] = release.name
        milestone = Milestone.get_current(release)
        context['milestone_name'] = milestone.name

        context['upstream_status'] = ''
        context['upstream_version'] = ''
        context['upstream_no_update_reason'] = ''
        recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
            milestone.start_date,
            milestone.end_date
        )
        if recipe_upstream_history:
            recipe_upstream = RecipeUpstream.get_by_recipe_and_history(
                recipe, recipe_upstream_history)
            if recipe_upstream:
                if recipe_upstream.status == 'N' and recipe_upstream.no_update_reason:
                    recipe_upstream.status = 'C'
                elif recipe_upstream.status == 'D':
                    recipe_upstream.status = 'U'
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

class MaintainerList():
    name = None
    recipes_all = 0
    recipes_up_to_date = '0'
    recipes_not_updated = '0'
    recipes_cant_be_updated = '0'
    recipes_unknown = '0'
    percentage_done = '0.00'

    interval_statistics = None

    def __init__(self, name):
        self.name = name

class MaintainerListView(ListView):
    context_object_name = 'maintainer_list'

    def get_queryset(self):
        maintainer_list = []
        self.maintainer_count = 0

        self.release_name = self.kwargs['release_name']
        release = get_object_or_404(Release, name=self.release_name)
        self.milestone_name = self.kwargs['milestone_name']
        milestone = get_object_or_404(Milestone, release = release,
                name=self.milestone_name)

        if "All" in milestone.name:
            intervals = milestone.get_milestone_intervals(release)
        else:
            intervals = milestone.get_week_intervals()

        self.milestone_statistics = _get_milestone_statistics(milestone)

        recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
            milestone.end_date)

        if recipe_maintainer_history:
            for rm in RecipeMaintainer.objects.filter(history =
                recipe_maintainer_history).values(
                'maintainer__name').distinct().order_by('maintainer__name'):
                maintainer_list.append(MaintainerList(rm['maintainer__name']))

            self.maintainer_count = len(maintainer_list)

        self.intervals = sorted(intervals.keys())
        current_date = date.today()
        for ml in maintainer_list:
            milestone_statistics = _get_milestone_statistics(milestone, ml.name)
            ml.recipes_all = milestone_statistics['all']
            ml.recipes_up_to_date = ('' if milestone_statistics['up_to_date'] == 0
                    else milestone_statistics['up_to_date'])
            ml.recipes_not_updated = ('' if milestone_statistics['not_updated'] == 0
                    else milestone_statistics['not_updated'])
            ml.recipes_cant_be_updated = ('' if milestone_statistics['cant_be_updated'] == 0
                    else milestone_statistics['cant_be_updated'])
            ml.recipes_unknown = ('' if milestone_statistics['unknown'] == 0
                    else milestone_statistics['unknown'])
            ml.percentage_done = milestone_statistics['percentage'] + '%'

            ml.interval_statistics = []
            self.current_interval = -1
            for idx, i in enumerate(sorted(intervals.keys())):
                start_date = intervals[i]['start_date']
                end_date = intervals[i]['end_date']

                if current_date >= start_date and current_date <= end_date:
                    self.current_interval = idx

                number = RecipeUpgrade.objects.filter(maintainer__name = ml.name,
                        commit_date__gte = start_date,
                        commit_date__lte = end_date).count()
                ml.interval_statistics.append('' if number == 0 else number)

        return maintainer_list

    def get_context_data(self, **kwargs):
        context = super(MaintainerListView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name

        context['release_name'] = self.release_name
        context['all_releases'] = Release.objects.filter().order_by('-end_date')
        context['milestone_name'] = self.milestone_name
        context['all_milestones'] = Milestone.objects.filter(release__name =
                self.release_name).order_by('-end_date')

        context['recipes_percentage'] = self.milestone_statistics['percentage']
        context['recipes_up_to_date'] = self.milestone_statistics['up_to_date']
        context['recipes_not_updated'] = self.milestone_statistics['not_updated']
        context['recipes_cant_be_updated'] = self.milestone_statistics['cant_be_updated']
        context['recipes_unknown'] = self.milestone_statistics['unknown']

        context['maintainer_count'] = self.maintainer_count
        context['intervals'] = self.intervals
        context['current_interval'] = self.current_interval

        return context

