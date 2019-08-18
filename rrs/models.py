# rrs-web - model definitions
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import re
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../')))

from datetime import date, datetime

from django.db import models
from django.contrib.auth.models import User
from layerindex.models import Recipe, LayerBranch, PythonEnvironment
from django.core.exceptions import ObjectDoesNotExist


class MaintenancePlan(models.Model):
    MAINTENANCEPLAN_MAINTAINER_STYLE = (
        ('I', 'Per-recipe - maintainers.inc'),
        ('L', 'Layer-wide'),
    )
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    updates_enabled = models.BooleanField('Enable updates', default=True, help_text='Enable automatically updating metadata for this plan via the update scripts')
    email_enabled = models.BooleanField('Enable emails', default=False, help_text='Enable automatically sending report emails for this plan')
    email_subject = models.CharField(max_length=255, blank=True, default='[Recipe reporting system] Upgradable recipe name list', help_text='Subject line of automated emails')
    email_from = models.CharField(max_length=255, blank=True, help_text='Sender for automated emails')
    email_to = models.CharField(max_length=255, blank=True, help_text='Recipient for automated emails (separate multiple addresses with ;)')
    admin = models.ForeignKey(User, blank=True, null=True, help_text='Plan administrator', on_delete=models.SET_NULL)
    maintainer_style = models.CharField(max_length=1, choices=MAINTENANCEPLAN_MAINTAINER_STYLE, default='L', help_text='Maintainer tracking style for the layers within this plan')

    def get_default_release(self):
        return self.release_set.filter(milestone__isnull=False).last()

    def per_recipe_maintainers(self):
        return self.maintainer_style != 'L'

    def __str__(self):
        return '%s' % (self.name)

class MaintenancePlanLayerBranch(models.Model):
    plan = models.ForeignKey(MaintenancePlan)
    layerbranch = models.ForeignKey(LayerBranch)
    python3_switch_date = models.DateTimeField('Commit date to switch to Python 3', default=datetime(2016, 6, 2))
    python2_environment = models.ForeignKey(PythonEnvironment, related_name='maintplan_layerbranch_python2_set', blank=True, null=True, help_text='Environment to use for Python 2 commits')
    python3_environment = models.ForeignKey(PythonEnvironment, related_name='maintplan_layerbranch_python3_set', blank=True, null=True, help_text='Environment to use for Python 3 commits')
    upgrade_date = models.DateTimeField('Recipe upgrade date', blank=True, null=True)
    upgrade_rev = models.CharField('Recipe upgrade revision ', max_length=80, blank=True)

    class Meta:
        verbose_name_plural = "Maintenance plan layer branches"

class Release(models.Model):
    plan = models.ForeignKey(MaintenancePlan)
    name = models.CharField(max_length=100)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

    class Meta:
        unique_together = ('plan', 'name',)

    def get_default_milestone(self):
        return self.milestone_set.last()

    @staticmethod
    def get_by_date(maintplan, date):
        release_qry = Release.objects.filter(plan=maintplan,
                start_date__lte = date,
                end_date__gte = date).order_by('-end_date')

        if release_qry:
            return release_qry[0]
        else:
            return None

    @staticmethod
    def get_current(maintplan):
        current = date.today()
        current_release = Release.get_by_date(maintplan, current)
        if current_release:
            return current_release
        else:
            plan_releases = Release.objects.filter(plan=maintplan).order_by('-end_date')
            if plan_releases:
                return plan_releases[0]
        return None

    def __str__(self):
        return '%s - %s' % (self.plan.name, self.name)

class Milestone(models.Model):
    release = models.ForeignKey(Release)
    name = models.CharField(max_length=100)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

    class Meta:
        unique_together = ('release', 'name',)

    """ Get milestones, filtering don't exist yet and ordering """
    @staticmethod
    def get_by_release_name(maintplan, release_name):
        milestones = []
        today = date.today()

        try:
            mall = Milestone.objects.get(release__plan=maintplan, release__name=release_name, name='All')
        except ObjectDoesNotExist:
            mall = None
        if mall:
            milestones.append(mall)

        mqry = Milestone.objects.filter(release__plan=maintplan, release__name=release_name).order_by('-end_date')
        for m in mqry:
            if m.name == 'All':
                continue

            if m.start_date > today:
                continue

            milestones.append(m)

        return milestones

    """ Get milestone by release and date """
    @staticmethod
    def get_by_release_and_date(release, date):
        milestone_set = Milestone.objects.filter(release = release,
                start_date__lte = date, end_date__gte = date). \
                exclude(name = 'All').order_by('-end_date')

        if milestone_set:
            return milestone_set[0]
        else:
            return None

    """ Get current milestone """
    @staticmethod
    def get_current(release):
        current_milestone =  None
        current_date = date.today()

        mqry = Milestone.objects.filter(release = release, start_date__lte = current_date,
                 end_date__gte = current_date).exclude(name = 'All').order_by('-end_date')
        if mqry:
            current_milestone = mqry[0]
        else:
            current_milestone = Milestone.objects.filter(release = release). \
                order_by('-end_date')[0]

        return current_milestone

    """ Get milestone intervals by release """ 
    @staticmethod
    def get_milestone_intervals(release):
        milestones = Milestone.objects.filter(release = release)

        milestone_dir = {}
        for m in milestones:
            if "All" in m.name:
                continue

            milestone_dir[m.name] = {}
            milestone_dir[m.name]['start_date'] = m.start_date
            milestone_dir[m.name]['end_date'] = m.end_date

        return milestone_dir

    """ Get week intervals from start and end of Milestone """ 
    def get_week_intervals(self):
        from datetime import timedelta

        weeks = {}

        week_delta = timedelta(weeks=1)
        week_no = 1
        current_date = self.start_date
        while True:
            if current_date >= self.end_date:
                break;

            weeks[week_no] = {}
            weeks[week_no]['start_date'] = current_date
            weeks[week_no]['end_date'] = current_date + week_delta
            current_date += week_delta
            week_no += 1

        return weeks

    def __str__(self):
        return '%s: %s %s' % (self.release.plan.name, self.release.name, self.name)


class RecipeSymbol(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    pn = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=200, blank=True)

    @staticmethod
    def symbol(pn, layerbranch, summary=None):
        rsym, created = RecipeSymbol.objects.get_or_create(pn=pn, layerbranch=layerbranch)
        if created:
            if summary:
                rsym.summary = summary
            else:
                recipe = Recipe.objects.filter(pn=pn, layerbranch=layerbranch).first()
                if recipe:
                    rsym.summary = recipe.summary
            rsym.save()
        return rsym

    def __str__(self):
        return "%s: %s" % (str(self.layerbranch), self.pn)


class Maintainer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    email = models.CharField(max_length=255, blank=True)

    """
        Create maintainer if no exist else update email.
        Return Maintainer.
    """
    @staticmethod
    def create_or_update(name, email):
        try:
            m = Maintainer.objects.get(name = name)
            m.email = email
        except Maintainer.DoesNotExist:
            m = Maintainer()
            m.name = name
            m.email = email

        m.save()

        return m

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return "%s <%s>" % (self.name, self.email)

class RecipeMaintainerHistory(models.Model):
    title = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(db_index=True)
    author = models.ForeignKey(Maintainer)
    sha1 = models.CharField(max_length=64)
    layerbranch = models.ForeignKey(LayerBranch)

    class Meta:
        unique_together = ('layerbranch', 'sha1',)

    @staticmethod
    def get_last(layerbranch):
        rmh_qry = RecipeMaintainerHistory.objects.filter(layerbranch=layerbranch).order_by('-date')

        if rmh_qry:
            return rmh_qry[0]
        else:
            return None

    @staticmethod
    def get_by_end_date(layerbranch, end_date):
        rmh_qry = RecipeMaintainerHistory.objects.filter(
                layerbranch=layerbranch,
                date__lte = end_date).order_by('-date')

        if rmh_qry:
            return rmh_qry[0]

        rmh_qry = RecipeMaintainerHistory.objects.filter(
                layerbranch=layerbranch
                ).order_by('date')
        if rmh_qry:
            return rmh_qry[0]
        else:
            return None

    def __str__(self):
        return "%s: %s, %s" % (self.date, self.author.name, self.sha1[:10])

class RecipeMaintainer(models.Model):
    recipesymbol = models.ForeignKey(RecipeSymbol)
    maintainer = models.ForeignKey(Maintainer)
    history = models.ForeignKey(RecipeMaintainerHistory)

    @staticmethod
    def get_maintainer_by_recipe_and_history(recipe, history):
        qry = RecipeMaintainer.objects.filter(recipesymbol__pn=recipe.pn,
                history=history)

        if qry:
            return qry[0].maintainer
        else:
            return None

    def __str__(self):
        return "%s: %s <%s>" % (self.recipesymbol.pn, self.maintainer.name,
                                self.maintainer.email)

class RecipeUpstreamHistory(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(db_index=True)

    @staticmethod
    def get_last_by_date_range(layerbranch, start, end):
        history = RecipeUpstreamHistory.objects.filter(layerbranch=layerbranch,
                start_date__gte = start,
                start_date__lte = end).order_by('-start_date')

        if history:
            return history[0]
        else:
            return None

    @staticmethod
    def get_first_by_date_range(layerbranch, start, end):
        history = RecipeUpstreamHistory.objects.filter(layerbranch=layerbranch,
                start_date__gte = start,
                start_date__lte = end).order_by('start_date')

        if history:
            return history[0]
        else:
            return None

    @staticmethod
    def get_last(layerbranch):
        history = RecipeUpstreamHistory.objects.filter(layerbranch=layerbranch).order_by('-start_date')

        if history:
            return history[0]
        else:
            return None

    def __str__(self):
        return '%s: %s' % (self.id, self.start_date)

class RecipeUpstream(models.Model):
    RECIPE_UPSTREAM_STATUS_CHOICES = (
        ('A', 'All'),
        ('N', 'Not updated'),
        ('C', 'Can\'t be updated'),
        ('Y', 'Up-to-date'),
        ('D', 'Downgrade'),
        ('U', 'Unknown'),
    )
    RECIPE_UPSTREAM_STATUS_CHOICES_DICT = dict(RECIPE_UPSTREAM_STATUS_CHOICES)

    RECIPE_UPSTREAM_TYPE_CHOICES = (
        ('A', 'Automatic'),
        ('M', 'Manual'),
    )
    RECIPE_UPSTREAM_TYPE_CHOICES_DICT = dict(RECIPE_UPSTREAM_TYPE_CHOICES)

    recipesymbol = models.ForeignKey(RecipeSymbol)
    history = models.ForeignKey(RecipeUpstreamHistory)
    version = models.CharField(max_length=100, blank=True)
    type = models.CharField(max_length=1, choices=RECIPE_UPSTREAM_TYPE_CHOICES, blank=True, db_index=True)
    status =  models.CharField(max_length=1, choices=RECIPE_UPSTREAM_STATUS_CHOICES, blank=True, db_index=True)
    no_update_reason = models.CharField(max_length=255, blank=True, db_index=True)
    date = models.DateTimeField(db_index=True)

    @staticmethod
    def get_all_recipes(history):
        qry = RecipeUpstream.objects.filter(history = history)
        return qry

    @staticmethod
    def get_recipes_not_updated(history):
        qry = RecipeUpstream.objects.filter(history = history, status = 'N',
                no_update_reason = '').order_by('pn')
        return qry

    @staticmethod
    def get_recipes_cant_be_updated(history):
        qry = RecipeUpstream.objects.filter(history = history, status = 'N') \
                .exclude(no_update_reason = '').order_by('pn')
        return qry

    @staticmethod
    def get_recipes_up_to_date(history):
        qry = RecipeUpstream.objects.filter(history = history, status = 'Y' \
                ).order_by('pn')
        return qry

    @staticmethod
    def get_recipes_unknown(history):
        qry = RecipeUpstream.objects.filter(history = history,
                status__in = ['U', 'D']).order_by('pn')
        return qry

    @staticmethod
    def get_by_recipe_and_history(recipesymbol, history):
        ru = RecipeUpstream.objects.filter(recipesymbol=recipesymbol, history=history)
        return ru[0] if ru else None

    def needs_upgrade(self):
        if self.status == 'N':
            return True
        else:
            return False

    def __str__(self):
        return '%s: (%s, %s, %s)' % (self.recipesymbol.pn, self.status,
                self.version, self.date)

class RecipeDistro(models.Model):
    recipe = models.ForeignKey(Recipe)
    distro = models.CharField(max_length=100, blank=True)
    alias = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return '%s: %s' % (self.recipe.pn, self.distro)

    @staticmethod
    def get_distros_by_recipe(recipe):
        recipe_distros = []

        query = RecipeDistro.objects.filter(recipe = recipe).order_by('distro')
        for q in query:
            recipe_distros.append(q.distro)

        return recipe_distros


class RecipeUpgradeGroup(models.Model):
    recipesymbol = models.ForeignKey(RecipeSymbol)
    title = models.CharField(max_length=100, help_text='Group title')

    def __str__(self):
        return '%s: %s' % (self.recipesymbol, self.title)


class RecipeUpgradeGroupRule(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    pn = models.CharField(max_length=100, help_text='Regular expression to match recipe to apply to')
    version = models.CharField(max_length=100, help_text='Regular expression to split version component on')

    @staticmethod
    def group_for_params(recipesymbol, version):
        for rule in RecipeUpgradeGroupRule.objects.filter(layerbranch=recipesymbol.layerbranch):
            if re.match(rule.pn, recipesymbol.pn):
                res = re.match(rule.version, version)
                if res:
                    if res.groups():
                        match = res.groups()[0]
                    else:
                        match = res.string[res.start(0):res.end(0)]
                    group, _ = RecipeUpgradeGroup.objects.get_or_create(recipesymbol=recipesymbol, title=match)
                    group.save()
                    return group
        return None

    def __str__(self):
        return '%s: %s' % (self.layerbranch, self.pn)


class RecipeUpgrade(models.Model):
    UPGRADE_TYPE_CHOICES = (
        ('U', 'Upgrade'),
        ('D', 'Downgrade'),
        ('N', 'Delete'),
        ('R', 'Delete (final)'),
        ('M', 'Move'),
    )

    recipesymbol = models.ForeignKey(RecipeSymbol)
    maintainer = models.ForeignKey(Maintainer, blank=True)
    sha1 = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=1024, blank=True)
    version = models.CharField(max_length=100, blank=True)
    author_date = models.DateTimeField(db_index=True)
    commit_date = models.DateTimeField(db_index=True)
    upgrade_type = models.CharField(max_length=1, choices=UPGRADE_TYPE_CHOICES, default='U', db_index=True)
    filepath = models.CharField(max_length=512, blank=True)
    orig_filepath = models.CharField(max_length=512, blank=True)
    group = models.ForeignKey(RecipeUpgradeGroup, blank=True, null=True, on_delete=models.SET_NULL)

    @staticmethod
    def get_by_recipe_and_date(recipe, end_date):
        ru = RecipeUpgrade.objects.filter(recipesymbol__pn=recipe.pn,
                recipesymbol__layerbranch=recipe.layerbranch,
                commit_date__lte = end_date)
        return ru[len(ru) - 1] if ru else None

    def short_sha1(self):
        return self.sha1[0:6]

    def commit_url(self):
        return self.recipesymbol.layerbranch.commit_url(self.sha1)

    def regroup(self):
        group = RecipeUpgradeGroupRule.group_for_params(self.recipesymbol, self.version)
        if group != self.group:
            self.group = group
            return True
        else:
            return False

    def __str__(self):
        if self.upgrade_type == 'R':
            return '%s: deleted [final] (%s)' % (self.recipesymbol.pn,
                            self.commit_date)
        elif self.upgrade_type == 'N':
            return '%s: deleted (%s)' % (self.recipesymbol.pn,
                            self.commit_date)
        elif self.upgrade_type == 'M':
            return '%s: moved (%s)' % (self.recipesymbol.pn,
                            self.commit_date)
        else:
            return '%s: (%s, %s)' % (self.recipesymbol.pn, self.version,
                            self.commit_date)


class RecipeMaintenanceLink(models.Model):
    pn_match = models.CharField(max_length=100, help_text='Expression to match against pn of recipes that should be linked (glob expression)')
    pn_target = models.CharField(max_length=100, help_text='Name of recipe to link to')

    @staticmethod
    def link_maintainer(pn, rmh):
        import fnmatch
        for rml in RecipeMaintenanceLink.objects.all():
            if fnmatch.fnmatch(pn, rml.pn_match):
                recipe_link_objs = rmh.layerbranch.recipe_set.filter(pn=rml.pn_target)
                if recipe_link_objs:
                    lrm = RecipeMaintainer.objects.filter(recipesymbol__pn=recipe_link_objs[0].pn, history=rmh)
                    if lrm:
                        return lrm[0]
        return None


    def __str__(self):
        return '%s -> %s' % (self.pn_match, self.pn_target)
