# rrs-web - model definitions
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import os.path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../')))

from datetime import date

from django.db import models
from django.db.models.query import Q
from layerindex.models import Recipe

class Release(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    @staticmethod
    def get_by_date(date):
        release_qry = Release.objects.filter(start_date__lte = date, 
                end_date__gte = date).order_by('-end_date')

        if release_qry:
            return release_qry[0]
        else:
            return None

    @staticmethod
    def get_current():
        current = date.today()
        current_release = Release.get_by_date(current)

        return current_release or Release.objects.filter().order_by('-end_date')[0]

    def __unicode__(self):
        return '%s' % (self.name)

class Milestone(models.Model):
    release = models.ForeignKey(Release)
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        unique_together = ('release', 'name',)

    """ Get milestones, filtering don't exist yet and ordering """
    @staticmethod
    def get_by_release_name(release_name):
        milestones = []
        today = date.today()

        mall = Milestone.objects.get(release__name = release_name, name = 'All')
        if mall:
            milestones.append(mall)

        mqry = Milestone.objects.filter(release__name = release_name).order_by('-end_date')
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

    def __unicode__(self):
        return '%s%s' % (self.release.name, self.name)

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

    def __unicode__(self):
        return "%s <%s>" % (self.name, self.email)

class RecipeMaintainerHistory(models.Model):
    title = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField()
    author = models.ForeignKey(Maintainer)
    sha1 = models.CharField(max_length=64, unique=True)

    @staticmethod
    def get_last():
        rmh_qry = RecipeMaintainerHistory.objects.filter().order_by('-date')

        if rmh_qry:
            return rmh_qry[0]
        else:
            return None

    @staticmethod
    def get_by_end_date(end_date):
        rmh_qry = RecipeMaintainerHistory.objects.filter(
                date__lte = end_date).order_by('-date')

        if rmh_qry:
            return rmh_qry[0]

        rmh_qry = RecipeMaintainerHistory.objects.filter(
                ).order_by('date')
        if rmh_qry:
            return rmh_qry[0]
        else:
            return None

    def __unicode__(self):
        return "%s: %s, %s" % (self.date, self.author.name, self.sha1[:10])

class RecipeMaintainer(models.Model):
    recipe = models.ForeignKey(Recipe)
    maintainer = models.ForeignKey(Maintainer)
    history = models.ForeignKey(RecipeMaintainerHistory)

    @staticmethod
    def get_maintainer_by_recipe_and_history(recipe, history):
        qry = RecipeMaintainer.objects.filter(recipe = recipe,
                history = history)

        if qry:
            return qry[0].maintainer
        else:
            return None

    def __unicode__(self):
        return "%s: %s <%s>" % (self.recipe.pn, self.maintainer.name,
                                self.maintainer.email)

class RecipeUpstreamHistory(models.Model):
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    @staticmethod
    def get_last_by_date_range(start, end):
        history = RecipeUpstreamHistory.objects.filter(start_date__gte = start, 
                start_date__lte = end).order_by('-start_date')

        if history:
            return history[0]
        else:
            return None

    @staticmethod
    def get_last():
        history = RecipeUpstreamHistory.objects.filter().order_by('-start_date')

        if history:
            return history[0]
        else:
            return None

    def __unicode__(self):
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

    recipe = models.ForeignKey(Recipe)
    history = models.ForeignKey(RecipeUpstreamHistory)
    version = models.CharField(max_length=100, blank=True)
    type = models.CharField(max_length=1, choices=RECIPE_UPSTREAM_TYPE_CHOICES, blank=True)
    status =  models.CharField(max_length=1, choices=RECIPE_UPSTREAM_STATUS_CHOICES, blank=True)
    no_update_reason = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField()

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
    def get_by_recipe_and_history(recipe, history):
        ru = RecipeUpstream.objects.filter(recipe = recipe, history = history)
        return ru[0] if ru else None

    def needs_upgrade(self):
        if self.status == 'N':
            return True
        else:
            return False

    def __unicode__(self):
        return '%s: (%s, %s, %s)' % (self.recipe.pn, self.status,
                self.version, self.date)

class RecipeDistro(models.Model):
    recipe = models.ForeignKey(Recipe)
    distro = models.CharField(max_length=100, blank=True)
    alias = models.CharField(max_length=100, blank=True)

    def __unicode__(self):
        return '%s: %s' % (self.recipe.pn, self.distro)

    @staticmethod
    def get_distros_by_recipe(recipe):
        recipe_distros = []

        query = RecipeDistro.objects.filter(recipe = recipe).order_by('distro')
        for q in query:
            recipe_distros.append(q.distro)

        return recipe_distros


class RecipeUpgrade(models.Model):
    recipe = models.ForeignKey(Recipe)
    maintainer = models.ForeignKey(Maintainer, blank=True)
    sha1 = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=1024, blank=True)
    version = models.CharField(max_length=100, blank=True)
    author_date = models.DateTimeField()
    commit_date = models.DateTimeField()

    @staticmethod
    def get_by_recipe_and_date(recipe, end_date):
        ru = RecipeUpgrade.objects.filter(recipe = recipe,
                commit_date__lte = end_date)
        return ru[0] if ru else None

    def short_sha1(self):
        return self.sha1[0:6]

    def commit_url(self):
        web_interface_url = self.recipe.layerbranch.layer.vcs_web_url
        return web_interface_url + "/commit/?id=" + self.sha1

    def __unicode__(self):
        return '%s: (%s, %s)' % (self.recipe.pn, self.version,
                        self.commit_date)
