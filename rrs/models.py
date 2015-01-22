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

        milestone_set = Milestone.objects.filter(start_date__lte = current, 
                end_date__gte = current).order_by('-id')

        if milestone_set:
            return milestone_set[0]
        else:
            return Milestone.objects.filter().order_by('-id')[0]

    """ Get month intervals between the start and the end of the milestone """ 
    def get_intervals(self):
        intervals = []
        previous_date = self.start_date
        current_date = self.start_date
        while current_date < self.end_date+timedelta(days=28):
            current_date += timedelta(days=1)
            if current_date.month != previous_date.month:
                interval_start = previous_date.replace(day=1)
                interval_end = current_date.replace(day=1)
                interval_end -= timedelta(days=1)
                intervals.append((interval_start, interval_end))
                previous_date = current_date
        return intervals

    def __unicode__(self):
        return '%s' % (self.name)

class Maintainer(models.Model):
    name = models.CharField(max_length=255, unique=True)
    email = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __unicode__(self):
        return "%s <%s>" % (self.name, self.email)

class RecipeMaintainer(models.Model):
    recipe = models.ForeignKey(Recipe)
    maintainer =  models.ForeignKey(Maintainer)

    @staticmethod
    def get_maintainer_by_recipe(recipe):
        recipe_maintainer = RecipeMaintainer.objects.filter(recipe = recipe)[0]
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
                start_date__lte = end).order_by('-id')

        if history:
            return history[0]
        else:
            return None

    @staticmethod
    def get_last():
        history = RecipeUpstreamHistory.objects.filter().order_by('-id')

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
    history = models.ForeignKey(RecipeUpstreamHistory, null=True)
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

class RecipeUpgrade(models.Model):
    recipe = models.ForeignKey(Recipe)
    maintainer = models.ForeignKey(Maintainer, blank=True, null=True)
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
