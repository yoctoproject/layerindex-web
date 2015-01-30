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
from layerindex.models import Recipe

class Milestone(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    """ Get current milestone """
    @staticmethod
    def get_current():
        current = date.today()
        current_milestone = Milestone.get_by_date(current)
        return current_milestone or Milestone.objects.filter().order_by('-id')[0]

    """ Get milestone by date """
    @staticmethod
    def get_by_date(date):
        milestone_set = Milestone.objects.filter(start_date__lte = date, 
                end_date__gte = date).order_by('-id')

        if milestone_set:
            return milestone_set[0]
        else:
            return None

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
        return '%s' % (self.name)

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
        recipe_maintainer = RecipeMaintainer.objects.filter(recipe = recipe,
                history = history)[0]
        return recipe_maintainer.maintainer

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

    def short_sha1(self):
        return self.sha1[0:6]

    def commit_url(self):
        web_interface_url = self.recipe.layerbranch.layer.vcs_web_url
        return web_interface_url + "/commit/?id=" + self.sha1

    def __unicode__(self):
        return '%s: (%s, %s)' % (self.recipe.pn, self.version,
                        self.commit_date)
