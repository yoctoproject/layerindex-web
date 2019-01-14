import urllib

import csv
from django.http import HttpResponse

from datetime import date, datetime
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, RedirectView
from django.core.urlresolvers import resolve, reverse, reverse_lazy
from django.db import connection
from django.contrib import messages

from layerindex.models import Recipe, StaticBuildDep, Patch
from rrs.models import Release, Milestone, Maintainer, RecipeMaintainerHistory, \
        RecipeMaintainer, RecipeUpstreamHistory, RecipeUpstream, \
        RecipeDistro, RecipeUpgrade, MaintenancePlan



class FrontPageRedirect(RedirectView):
    permanent = False

    def get_redirect_url(self):
        maintplan = MaintenancePlan.objects.first()
        if not maintplan:
            raise Exception('No maintenance plans defined')
        release = Release.get_current(maintplan)
        if not release:
            raise Exception('No releases defined for maintenance plan %s' % maintplan.name)
        milestone = Milestone.get_current(release)
        if not milestone:
            raise Exception('No milestones defined for release %s' % release.name)
        return reverse('rrs_recipes', args=(maintplan.name, release.name, milestone.name))

class MaintenancePlanRedirect(RedirectView):
    permanent = False

    def get_redirect_url(self, maintplan_name):
        maintplan = get_object_or_404(MaintenancePlan, name=maintplan_name)
        release = Release.get_current(maintplan)
        if not release:
            raise Exception('No releases defined for maintenance plan %s' % maintplan.name)
        milestone = Milestone.get_current(release)
        if not milestone:
            raise Exception('No milestones defined for release %s' % release.name)
        return reverse('rrs_recipes', args=(maintplan.name, release.name, milestone.name))


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
    return reverse_lazy('layer_item', args=(branch, layer_name))

class Raw():
    """ Raw SQL call to improve performance

        Table abbrevations:
        re:     Recipe
        ma:     Maintainer
        reup:   Recipe Upstream
        reupg:  Recipe Ugrade
        rema:   Recipe Maintainer
        remahi: Recipe Maintainer History
    """

    @staticmethod
    def get_re_by_mantainer_and_date(maintainer, date_id):
        """ Get Recipes based on Maintainer and Recipe Maintainer History """
        recipes = []
        cur = connection.cursor()

        cur.execute("""SELECT DISTINCT rema.recipe_id
                        FROM rrs_recipemaintainer AS rema
                        INNER JOIN rrs_maintainer AS ma
                        ON rema.maintainer_id = ma.id
                        WHERE rema.history_id = %s 
                        AND ma.name = %s;
                    """, [date_id, maintainer])

        for re in cur.fetchall():
            recipes.append(re[0])
        return recipes

    @staticmethod
    def get_ma_by_recipes_and_date(recipes_id, date_id=None):
        """ Get Maintainer based on Recipes and Recipe Upstream History """
        stats = []

        if date_id:
            qry = """SELECT rema.recipe_id, ma.name
                    FROM rrs_recipemaintainer AS rema
                    INNER JOIN rrs_maintainer AS ma
                    ON rema.maintainer_id = ma.id
                    WHERE rema.history_id = %s
                    AND rema.recipe_id IN %s;"""
            cur = connection.cursor()
            cur.execute(qry, [str(date_id), tuple(recipes_id)])
            stats = Raw.dictfetchall(cur)

        return stats

    @staticmethod
    def get_reup_statistics(maintplan, date, date_id):
        """ Special case to get recipes statistics removing gcc-source duplicates """
        recipes = []
        updated = 0
        not_updated = 0
        cant = 0
        unknown = 0

        for maintplanlayer in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = maintplanlayer.layerbranch
            layerbranch_recipes = Raw.get_reupg_by_date(layerbranch.id, date)
            for re in layerbranch_recipes:
                recipes.append(re["id"])

        if date_id and recipes:
            qry = """SELECT id, status, no_update_reason
                    FROM rrs_recipeupstream
                    WHERE history_id = %s
                    AND recipe_id IN %s;"""
            cur = connection.cursor()
            cur.execute(qry, [str(date_id.id), tuple(recipes)])

            for re in Raw.dictfetchall(cur):
                if re["status"] == "Y":
                    updated += 1
                elif re["status"]  == "N" and re["no_update_reason"] == "":
                    not_updated += 1
                elif re["status"] == "N":
                    cant += 1
                # We count downgrade as unknown
                else:
                    unknown += 1

        return (updated, not_updated, cant, unknown)

    @staticmethod
    def get_reup_by_recipes_and_date(recipes_id, date_id=None):
        """ Get Recipe Upstream based on Recipes and Recipe Upstream History """
        stats = []

        if date_id:
            qry = """SELECT recipe_id, status, no_update_reason, version
                    FROM rrs_recipeupstream
                    WHERE history_id = %s
                    AND recipe_id IN %s;"""
            cur = connection.cursor()
            cur.execute(qry, [str(date_id), tuple(recipes_id)])
            stats = Raw.dictfetchall(cur)

        return stats

    @staticmethod
    def get_reup_by_last_updated(layerbranch_id, date):
        """ Get last time the Recipes were upgraded """
        cur = connection.cursor()
        cur.execute("""SELECT recipe_id, MAX(commit_date) AS date
                       FROM rrs_recipeupgrade
                       INNER JOIN layerindex_recipe AS re
                       ON rrs_recipeupgrade.recipe_id = re.id
                       WHERE commit_date <= %s
                       AND re.layerbranch_id = %s
                       GROUP BY recipe_id;
                    """, [date, layerbranch_id])
        return Raw.dictfetchall(cur)

    @staticmethod
    def get_reup_by_date(date_id):
        """ Get Recipes not up to date based on Recipe Upstream History """
        cur = connection.cursor()
        cur.execute("""SELECT DISTINCT recipe_id
                        FROM rrs_recipeupstream
                        WHERE status = 'N'
                        AND history_id = %s
                    """, [date_id])
        return [i[0] for i in cur.fetchall()]

    @staticmethod
    def get_reupg_by_date(layerbranch_id, date):
        """ Get info for Recipes for the milestone """
        cur = connection.cursor()
        cur.execute("""SELECT re.id, re.pn, re.summary, te.version, rownum FROM (
                            SELECT recipe_id, version, commit_date, ROW_NUMBER() OVER(
                                PARTITION BY recipe_id
                                ORDER BY commit_date DESC
                            ) AS rownum
                        FROM rrs_recipeupgrade
                        WHERE commit_date <= %s) AS te
                        INNER JOIN layerindex_recipe AS re
                        ON te.recipe_id = re.id
                        WHERE rownum = 1
                        AND re.layerbranch_id = %s
                        ORDER BY re.pn;
                        """, [date, layerbranch_id])
        return Raw.dictfetchall(cur)

    @staticmethod
    def get_reupg_by_dates_and_recipes(start_date, end_date, recipes_id):
        """  Get Recipe Upgrade for the milestone based on Recipes """
        cur = connection.cursor()
        qry = """SELECT DISTINCT recipe_id
                FROM rrs_recipeupgrade
                WHERE commit_date >= %s
                AND commit_date <= %s
                AND recipe_id IN %s;"""
        cur.execute(qry, [start_date, end_date, tuple(recipes_id)])
        return Raw.dictfetchall(cur)

    @staticmethod
    def get_remahi_by_end_date(layerbranch_id, date):
        """ Get the latest Recipe Maintainer History for the milestone """
        cur = connection.cursor()

        cur.execute("""SELECT id
                        FROM rrs_recipemaintainerhistory
                        WHERE date <= %s
                        AND layerbranch_id = %s
                        ORDER BY date DESC
                        LIMIT 1;
                    """, [str(date), layerbranch_id])

        ret = cur.fetchone()

        if not ret:
            cur.execute("""SELECT id
                        FROM rrs_recipemaintainerhistory
                        WHERE layerbranch_id = %s
                        ORDER BY date
                        LIMIT 1;
                        """, [layerbranch_id])
            ret = cur.fetchone()

        return ret

    @staticmethod
    def dictfetchall(cursor):
        "Returns all rows from a cursor as a dict"
        desc = cursor.description
        return [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
        ]


def _get_milestone_statistics(milestone, maintainer_name=None):
    milestone_statistics = {}

    milestone_statistics['all'] = 0
    milestone_statistics['up_to_date'] = 0
    milestone_statistics['not_updated'] = 0
    milestone_statistics['cant_be_updated'] = 0
    milestone_statistics['unknown'] = 0

    if maintainer_name is None:
        milestone_statistics['all_upgraded'] = 0
        milestone_statistics['all_not_upgraded'] = 0

    for maintplanlayer in milestone.release.plan.maintenanceplanlayerbranch_set.all():
        layerbranch = maintplanlayer.layerbranch

        recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
            layerbranch,
            milestone.start_date,
            milestone.end_date
        )
        recipe_upstream_history_first = \
            RecipeUpstreamHistory.get_first_by_date_range(
                layerbranch,
                milestone.start_date,
                milestone.end_date,
        )

        if maintainer_name is None:
            t_updated, t_not_updated, t_cant, t_unknown = \
                Raw.get_reup_statistics(milestone.release.plan, milestone.end_date, recipe_upstream_history)
            milestone_statistics['all'] += \
                t_updated + t_not_updated + t_cant + t_unknown
            milestone_statistics['up_to_date'] = +t_updated
            milestone_statistics['not_updated'] = +t_not_updated
            milestone_statistics['cant_be_updated'] += t_cant
            milestone_statistics['unknown'] += t_unknown

            if recipe_upstream_history_first:
                recipes_not_upgraded = \
                    Raw.get_reup_by_date(recipe_upstream_history_first.id)
                if recipes_not_upgraded:
                    recipes_upgraded = \
                        Raw.get_reupg_by_dates_and_recipes(
                            milestone.start_date, milestone.end_date, recipes_not_upgraded)
                    milestone_statistics['all_upgraded'] += len(recipes_upgraded)
                    milestone_statistics['all_not_upgraded'] += len(recipes_not_upgraded)

        else:
            recipe_maintainer_history = Raw.get_remahi_by_end_date(
                    layerbranch.id, milestone.end_date)
            recipe_maintainer_all = Raw.get_re_by_mantainer_and_date(
                    maintainer_name, recipe_maintainer_history[0])
            milestone_statistics['all'] += len(recipe_maintainer_all)
            if recipe_upstream_history:
                recipe_upstream_all = Raw.get_reup_by_recipes_and_date(
                        recipe_maintainer_all, recipe_upstream_history.id)
            else:
                recipe_upstream_all = Raw.get_reup_by_recipes_and_date(
                        recipe_maintainer_all)

            for ru in recipe_upstream_all:
                if ru['status'] == 'Y':
                    milestone_statistics['up_to_date'] += 1
                elif ru['status'] == 'N':
                    if ru['no_update_reason'] == '':
                        milestone_statistics['not_updated'] += 1
                    else:
                        milestone_statistics['cant_be_updated'] += 1
                else:
                    milestone_statistics['unknown'] += 1


    milestone_statistics['percentage'] = '0'
    if maintainer_name is None:
        if milestone_statistics['all'] > 0:
            milestone_statistics['percentage_up_to_date'] = "%.0f" % \
                (float(milestone_statistics['up_to_date']) * 100.0 \
                /float(milestone_statistics['all']))
            milestone_statistics['percentage_not_updated'] = "%.0f" % \
                (float(milestone_statistics['not_updated']) * 100.0 \
                /float(milestone_statistics['all']))
            milestone_statistics['percentage_cant_be_updated'] = "%.0f" % \
                (float(milestone_statistics['cant_be_updated']) * 100.0 \
                /float(milestone_statistics['all']))
            milestone_statistics['percentage_unknown'] = "%.0f" % \
                (float(milestone_statistics['unknown']) * 100.0
                /float(milestone_statistics['all']))
            if milestone_statistics['all_not_upgraded'] > 0:
                milestone_statistics['percentage'] = "%.0f" % \
                    ((float(milestone_statistics['all_upgraded']) * 100.0)
                    /float(milestone_statistics['all_not_upgraded']))
        else:
            milestone_statistics['percentage_up_to_date'] = "0"
            milestone_statistics['percentage_not_updated'] = "0"
            milestone_statistics['percentage_cant_be_updated'] = "0"
            milestone_statistics['percentage_unknown'] = "0"
    else:
        if milestone_statistics['all'] > 0:
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
    outdated = None
    maintainer_name = None
    no_update_reason = None

    def __init__(self, pk, name, summary):
        self.pk = pk
        self.name = name
        self.summary = summary

def _get_recipe_list(milestone):
    recipe_list = []
    recipes_ids = []
    recipe_upstream_dict_all = {}
    recipe_last_updated_dict_all = {}
    maintainers_dict_all = {}
    current_date = date.today()

    for maintplanlayer in milestone.release.plan.maintenanceplanlayerbranch_set.all():
        layerbranch = maintplanlayer.layerbranch

        recipe_maintainer_history = Raw.get_remahi_by_end_date(layerbranch.id,
                    milestone.end_date)

        recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
            layerbranch,
            milestone.start_date,
            milestone.end_date
        )

        recipes = Raw.get_reupg_by_date(layerbranch.id, milestone.end_date)
        for i,re in enumerate(recipes):
            if 'pv' in re:
                recipes[i]['version'] = re['pv']
            recipes_ids.append(re['id'])

        if recipes:
            recipe_last_updated = Raw.get_reup_by_last_updated(
                    layerbranch.id, milestone.end_date)
            for rela in recipe_last_updated:
                recipe_last_updated_dict_all[rela['recipe_id']] = rela

            if recipe_upstream_history:
                recipe_upstream_all = Raw.get_reup_by_recipes_and_date(
                    recipes_ids, recipe_upstream_history.id)
                for reup in recipe_upstream_all:
                    recipe_upstream_dict_all[reup['recipe_id']] = reup

            if recipe_maintainer_history:
                maintainers_all = Raw.get_ma_by_recipes_and_date(
                    recipes_ids, recipe_maintainer_history[0])
                for ma in maintainers_all:
                    maintainers_dict_all[ma['recipe_id']] = ma['name']

    for recipe in recipes:
        upstream_version = ''
        upstream_status = ''
        no_update_reason = ''
        outdated = ''

        if recipe_upstream_history:
            recipe_upstream = recipe_upstream_dict_all.get(recipe['id'])
            if not recipe_upstream:
                recipe_add =  Recipe.objects.filter(id = recipe['id'])[0]
                recipe_upstream_add = RecipeUpstream()
                recipe_upstream_add.history = recipe_upstream_history
                recipe_upstream_add.recipe = recipe_add
                recipe_upstream_add.version = ''
                recipe_upstream_add.type = 'M' # Manual
                recipe_upstream_add.status = 'U' # Unknown
                recipe_upstream_add.no_update_reason = ''
                recipe_upstream_add.date = recipe_upstream_history.end_date
                recipe_upstream_add.save()
                recipe_upstream = {'version': '', 'status': 'U', 'type': 'M',
                        'no_update_reason': ''}

            if recipe_upstream['status'] == 'N' and recipe_upstream['no_update_reason']:
                recipe_upstream['status'] = 'C'
            upstream_status = \
                    RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT[
                        recipe_upstream['status']]
            if upstream_status == 'Downgrade':
                upstream_status = 'Unknown' # Downgrade is displayed as Unknown
            upstream_version = recipe_upstream['version']
            no_update_reason = recipe_upstream['no_update_reason']

            #Get how long the recipe hasn't been updated
            recipe_last_updated = \
                recipe_last_updated_dict_all.get(recipe['id'])
            if recipe_last_updated:
                recipe_date = recipe_last_updated['date']
                outdated = recipe_date.date().isoformat()
            else:
                outdated = ""

        maintainer_name =  maintainers_dict_all.get(recipe['id'], '')
        recipe_list_item = RecipeList(recipe['id'], recipe['pn'], recipe['summary'])
        recipe_list_item.version = recipe['version']
        recipe_list_item.upstream_status = upstream_status
        recipe_list_item.upstream_version = upstream_version
        recipe_list_item.outdated = outdated
        patches = Patch.objects.filter(recipe__id=recipe['id'])
        recipe_list_item.patches_total = patches.count()
        recipe_list_item.patches_pending = patches.filter(status='P').count()
        recipe_list_item.maintainer_name = maintainer_name
        recipe_list_item.no_update_reason = no_update_reason
        recipe_list.append(recipe_list_item)

    return recipe_list

class RecipeListView(ListView):
    context_object_name = 'recipe_list'

    def get_queryset(self):
        self.maintplan_name = self.kwargs['maintplan_name']
        maintplan = get_object_or_404(MaintenancePlan, name=self.maintplan_name)
        self.release_name = self.kwargs['release_name']
        release = get_object_or_404(Release, plan=maintplan, name=self.release_name)

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

        if 'search' in self.request.GET.keys():
            self.search = self.request.GET['search']

            # only allow one type of filter search or upstream_status/maintainer
            self.upstream_status = 'All'
            self.maintainer_name = 'All'
        else:
            self.search = ''

        _check_url_params(self.upstream_status, self.maintainer_name)

        self.milestone_statistics = _get_milestone_statistics(milestone)

        self.recipe_maintainer_history = {}
        for maintplanlayer in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = maintplanlayer.layerbranch
            self.recipe_maintainer_history[layerbranch.id] = RecipeMaintainerHistory.get_by_end_date(layerbranch,
                                                                                                     milestone.end_date)

        recipe_list = _get_recipe_list(milestone)
        self.recipe_list_count = len(recipe_list)

        return recipe_list

    def get_context_data(self, **kwargs):
        context = super(RecipeListView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name

        context['all_maintplans'] = MaintenancePlan.objects.all()
        context['maintplan_name'] = self.maintplan_name
        maintplan = get_object_or_404(MaintenancePlan, name=self.maintplan_name)
        context['maintplan'] = maintplan
        context['release_name'] = self.release_name
        context['all_releases'] = Release.objects.filter(plan=maintplan).order_by('-end_date')
        context['milestone_name'] = self.milestone_name
        context['all_milestones'] = Milestone.get_by_release_name(maintplan, self.release_name)

        current = date.today()
        current_release = Release.get_by_date(maintplan, current)
        if current_release:
            current_milestone = Milestone.get_by_release_and_date(current_release, current)
            if not current_milestone:
                messages.error(self.request, 'There is no milestone defined in the latest release (%s) that covers the current date, so data shown here is not up-to-date. The administrator will need to create a milestone in order to fix this.' % current_release)
        else:
            messages.error(self.request, 'There is no release defined that covers the current date, so data shown here is not up-to-date. The administrator will need to create a release (and corresponding milestones) in order to fix this.')

        context['recipes_percentage'] = self.milestone_statistics['percentage']
        context['recipes_all_upgraded'] = self.milestone_statistics['all_upgraded']
        context['recipes_all_not_upgraded'] = self.milestone_statistics['all_not_upgraded']
        context['recipes_up_to_date'] = self.milestone_statistics['up_to_date']
        context['recipes_not_updated'] = self.milestone_statistics['not_updated']
        context['recipes_cant_be_updated'] = self.milestone_statistics['cant_be_updated']
        context['recipes_unknown'] = self.milestone_statistics['unknown']
        context['recipes_percentage_up_to_date'] = \
            self.milestone_statistics['percentage_up_to_date']
        context['recipes_percentage_not_updated'] = \
            self.milestone_statistics['percentage_not_updated']
        context['recipes_percentage_cant_be_updated'] = \
            self.milestone_statistics['percentage_cant_be_updated']
        context['recipes_percentage_unknown'] = \
            self.milestone_statistics['percentage_unknown']

        context['recipe_list_count'] = self.recipe_list_count

        context['upstream_status'] = self.upstream_status
        ruch = RecipeUpstream.RECIPE_UPSTREAM_STATUS_CHOICES_DICT
        context['upstream_status_set_choices'] = [ruch['A']]
        context['upstream_status_choices'] = [ruch['N'], ruch['C'], ruch['Y'], ruch['U']]

        context['maintainer_name'] = self.maintainer_name
        context['set_maintainers'] =  ['All', 'No maintainer']
        all_maintainers = []
        for layerbranch_id, rmh in self.recipe_maintainer_history.items():
            for rm in RecipeMaintainer.objects.filter(history=rmh).values(
                    'maintainer__name').distinct().order_by('maintainer__name'):
                if rm['maintainer__name'] in context['set_maintainers']:
                    continue
                all_maintainers.append(rm['maintainer__name'])
        context['all_maintainers'] = all_maintainers

        context['search'] = self.search

        return context

def recipes_report(request, maintplan_name, release_name, milestone_name):
    maintplan = get_object_or_404(MaintenancePlan, name=maintplan_name)
    release = get_object_or_404(Release, plan=maintplan, name=release_name)
    milestone = get_object_or_404(Milestone, release = release, name=milestone_name)

    recipe_list = _get_recipe_list(milestone)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s_%s.csv"' % (
           release_name , milestone_name)

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
    maintplan_name = None
    release_name = None
    milestone_name = None
    date = None
    maintainer_name = None
    is_recipe_maintainer = None
    commit = None
    commit_url = None

    def __init__(self, title, version, maintplan_name, release_name, milestone_name, date, 
            maintainer_name, is_recipe_maintainer, commit, commit_url):
        self.title = title
        self.version = version
        self.maintplan_name = maintplan_name
        self.release_name = release_name
        self.milestone_name = milestone_name
        self.date = date
        self.maintainer_name = maintainer_name
        self.is_recipe_maintainer = is_recipe_maintainer
        self.commit = commit
        self.commit_url = commit_url

def _get_recipe_upgrade_detail(maintplan, recipe_upgrade):
    release_name = ''
    milestone_name = ''
    recipe_maintainer_history = None

    release = Release.get_by_date(maintplan, recipe_upgrade.commit_date)
    if release:
        release_name = release.name
        milestone = Milestone.get_by_release_and_date(release,
                recipe_upgrade.commit_date)
        if milestone:
            milestone_name = milestone.name
            recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
                recipe_upgrade.recipe.layerbranch,
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

    commit_date = recipe_upgrade.commit_date.date().isoformat()
    commit = recipe_upgrade.sha1[:10]
    commit_url = recipe_upgrade.recipe.layerbranch.commit_url(recipe_upgrade.sha1)

    rud = RecipeUpgradeDetail(recipe_upgrade.title, recipe_upgrade.version, \
            maintplan.name, release_name, milestone_name, commit_date, maintainer_name, \
            is_recipe_maintainer, commit, commit_url)

    return rud

class RecipeDetailView(DetailView):
    model = Recipe

    def get_queryset(self):
        self.maintplan_name = self.kwargs['maintplan_name']
        return super(RecipeDetailView, self).get_queryset()

    def get_context_data(self, **kwargs):
        context = super(RecipeDetailView, self).get_context_data(**kwargs)
        recipe = self.get_object()
        if not recipe:
            raise django.http.Http404

        maintplan = get_object_or_404(MaintenancePlan, name=self.maintplan_name)
        context['maintplan_name'] = maintplan.name
        context['maintplan'] = maintplan
        release = Release.get_current(maintplan)
        context['release_name'] = release.name
        milestone = Milestone.get_current(release)
        context['milestone_name'] = milestone.name

        context['upstream_status'] = ''
        context['upstream_version'] = ''
        context['upstream_no_update_reason'] = ''
        recipe_upstream_history = RecipeUpstreamHistory.get_last_by_date_range(
            recipe.layerbranch,
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

        self.recipe_maintainer_history = RecipeMaintainerHistory.get_last(recipe.layerbranch)
        recipe_maintainer = RecipeMaintainer.objects.filter(recipe = recipe,
                history = self.recipe_maintainer_history)
        if recipe_maintainer:
            maintainer = recipe_maintainer[0].maintainer
            context['maintainer_name'] = maintainer.name
        else:
            context['maintainer_name'] = 'No maintainer'

        context['recipe_upgrade_details'] = []
        for ru in RecipeUpgrade.objects.filter(recipe =
                recipe).order_by('-commit_date'): 
            context['recipe_upgrade_details'].append(_get_recipe_upgrade_detail(maintplan, ru))
        context['recipe_upgrade_detail_count'] = len(context['recipe_upgrade_details'])

        context['recipe_layer_branch_url'] = _get_layer_branch_url(
                recipe.layerbranch.branch.name, recipe.layerbranch.layer.name)

        context['recipe_provides'] = []
        for p in recipe.provides.split():
            context['recipe_provides'].append(p)

        context['recipe_depends'] = StaticBuildDep.objects.filter(recipes__id=recipe.id).values_list('name', flat=True)

        context['recipe_distros'] = RecipeDistro.get_distros_by_recipe(recipe)

        context['otherbranch_recipes'] = Recipe.objects.filter(layerbranch__layer=recipe.layerbranch.layer, layerbranch__branch__comparison=False, pn=recipe.pn).order_by('layerbranch__branch__sort_priority')

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

        self.maintplan_name = self.kwargs['maintplan_name']
        maintplan = get_object_or_404(MaintenancePlan, name=self.maintplan_name)
        self.release_name = self.kwargs['release_name']
        release = get_object_or_404(Release, plan=maintplan, name=self.release_name)
        self.milestone_name = self.kwargs['milestone_name']
        milestone = get_object_or_404(Milestone, release = release,
                name=self.milestone_name)

        if "All" in milestone.name:
            intervals = milestone.get_milestone_intervals(release)
            interval_type = 'Milestone'
        else:
            intervals = milestone.get_week_intervals()
            interval_type = 'Week'

        self.milestone_statistics = _get_milestone_statistics(milestone)

        self.maintainer_count = 0
        for maintplanlayer in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = maintplanlayer.layerbranch

            recipe_maintainer_history = RecipeMaintainerHistory.get_by_end_date(
                layerbranch, milestone.end_date)

            if recipe_maintainer_history:
                for rm in RecipeMaintainer.objects.filter(history =
                        recipe_maintainer_history).values(
                        'maintainer__name').distinct().order_by('maintainer__name'):
                    maintainer_list.append(MaintainerList(rm['maintainer__name']))

                self.maintainer_count += len(maintainer_list)

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

        # To add Wk prefix after get statics to avoid sorting problems
        if interval_type == 'Week':
            self.intervals = ['Wk' + str(i) for i in self.intervals]

        return maintainer_list

    def get_context_data(self, **kwargs):
        context = super(MaintainerListView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name

        context['all_maintplans'] = MaintenancePlan.objects.all()
        context['maintplan_name'] = self.maintplan_name
        maintplan = get_object_or_404(MaintenancePlan, name=self.maintplan_name)
        context['release_name'] = self.release_name
        context['all_releases'] = Release.objects.filter(plan=maintplan).order_by('-end_date')
        context['milestone_name'] = self.milestone_name
        context['all_milestones'] = Milestone.get_by_release_name(maintplan, self.release_name)

        context['recipes_percentage'] = self.milestone_statistics['percentage']
        context['recipes_all_upgraded'] = self.milestone_statistics['all_upgraded']
        context['recipes_all_not_upgraded'] = self.milestone_statistics['all_not_upgraded']
        context['recipes_up_to_date'] = self.milestone_statistics['up_to_date']
        context['recipes_not_updated'] = self.milestone_statistics['not_updated']
        context['recipes_cant_be_updated'] = self.milestone_statistics['cant_be_updated']
        context['recipes_unknown'] = self.milestone_statistics['unknown']
        context['recipes_percentage_up_to_date'] = \
            self.milestone_statistics['percentage_up_to_date']
        context['recipes_percentage_not_updated'] = \
            self.milestone_statistics['percentage_not_updated']
        context['recipes_percentage_cant_be_updated'] = \
            self.milestone_statistics['percentage_cant_be_updated']
        context['recipes_percentage_unknown'] = \
            self.milestone_statistics['percentage_unknown']

        context['maintainer_count'] = self.maintainer_count
        context['intervals'] = self.intervals
        context['interval_range'] = range(len(self.intervals))
        if hasattr(self, 'current_interval'):
                context['current_interval'] = self.current_interval

        return context


class MaintenanceStatsView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super(MaintenanceStatsView, self).get_context_data(**kwargs)

        context['this_url_name'] = resolve(self.request.path_info).url_name

        self.maintplan_name = self.kwargs['maintplan_name']
        maintplan = get_object_or_404(MaintenancePlan, name=self.maintplan_name)
        self.release_name = self.kwargs['release_name']
        release = get_object_or_404(Release, plan=maintplan, name=self.release_name)
        self.milestone_name = self.kwargs['milestone_name']
        milestone = get_object_or_404(Milestone, release = release, name=self.milestone_name)

        self.milestone_statistics = _get_milestone_statistics(milestone)

        context['recipes_percentage'] = self.milestone_statistics['percentage']
        context['recipes_all_upgraded'] = self.milestone_statistics['all_upgraded']
        context['recipes_all_not_upgraded'] = self.milestone_statistics['all_not_upgraded']
        context['recipes_up_to_date'] = self.milestone_statistics['up_to_date']
        context['recipes_not_updated'] = self.milestone_statistics['not_updated']
        context['recipes_cant_be_updated'] = self.milestone_statistics['cant_be_updated']
        context['recipes_unknown'] = self.milestone_statistics['unknown']
        context['recipes_percentage_up_to_date'] = \
            self.milestone_statistics['percentage_up_to_date']
        context['recipes_percentage_not_updated'] = \
            self.milestone_statistics['percentage_not_updated']
        context['recipes_percentage_cant_be_updated'] = \
            self.milestone_statistics['percentage_cant_be_updated']
        context['recipes_percentage_unknown'] = \
            self.milestone_statistics['percentage_unknown']

        # *** Upstream status chart ***
        statuses = []
        status_counts = {}
        statuses.append('Up-to-date')
        status_counts['Up-to-date'] = self.milestone_statistics['up_to_date']
        statuses.append('Not updated')
        status_counts['Not updated'] = self.milestone_statistics['not_updated']
        statuses.append('Can\'t be updated')
        status_counts['Can\'t be updated'] = self.milestone_statistics['cant_be_updated']
        statuses.append('Unknown')
        status_counts['Unknown'] = self.milestone_statistics['unknown']

        statuses = sorted(statuses, key=lambda status: status_counts[status], reverse=True)
        context['chart_upstream_status_labels'] = statuses
        context['chart_upstream_status_values'] = [status_counts[k] for k in statuses]

        # *** Patch status chart ***
        patch_statuses = []
        patch_status_counts = {}
        for maintplanlayer in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = maintplanlayer.layerbranch
            patches = Patch.objects.filter(recipe__layerbranch=layerbranch)
            for choice, desc in Patch.PATCH_STATUS_CHOICES:
                if desc not in patch_statuses:
                    patch_statuses.append(desc)
                patch_status_counts[desc] = patch_status_counts.get(desc, 0) + patches.filter(status=choice).count()

        patch_statuses = sorted(patch_statuses, key=lambda status: patch_status_counts[status], reverse=True)
        context['chart_patch_status_labels'] = patch_statuses
        context['chart_patch_status_values'] = [patch_status_counts[k] for k in patch_statuses]

        return context


