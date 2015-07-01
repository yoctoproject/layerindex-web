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
from django.db import connection
from django.db.models.query import Q
from layerindex.models import Recipe

class Release(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

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
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

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
    date = models.DateTimeField(db_index=True)
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
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(db_index=True)

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
    type = models.CharField(max_length=1, choices=RECIPE_UPSTREAM_TYPE_CHOICES, blank=True, db_index=True)
    status =  models.CharField(max_length=1, choices=RECIPE_UPSTREAM_STATUS_CHOICES, blank=True, db_index=True)
    no_update_reason = models.CharField(max_length=255, blank=True, db_index=True)
    date = models.DateTimeField(db_index=True)

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
    author_date = models.DateTimeField(db_index=True)
    commit_date = models.DateTimeField(db_index=True)

    @staticmethod
    def get_by_recipe_and_date(recipe, end_date):
        ru = RecipeUpgrade.objects.filter(recipe = recipe,
                commit_date__lte = end_date)
        return ru[len(ru) - 1] if ru else None

    def short_sha1(self):
        return self.sha1[0:6]

    def commit_url(self):
        web_interface_url = self.recipe.layerbranch.layer.vcs_web_url
        return web_interface_url + "/commit/?id=" + self.sha1

    def __unicode__(self):
        return '%s: (%s, %s)' % (self.recipe.pn, self.version,
                        self.commit_date)

class Raw():

    @staticmethod
    def get_remahi_by_end_date(date):
        cur = connection.cursor()

        cur.execute("""SELECT id
                FROM rrs_RecipeMaintainerHistory
                WHERE date <= %s
                ORDER BY date DESC
                LIMIT 1;
                """, [str(date)])

        ret = cur.fetchone()

        if not ret:
            cur.execute("""SELECT id
                FROM rrs_RecipeMaintainerHistory
                ORDER BY date
                LIMIT 1;""")
            ret = cur.fetchone()

        return ret

    @staticmethod
    def get_re_by_mantainer_and_date(maintainer, date_id):
        recipes = []
        cur = connection.cursor()

        cur.execute("""SELECT DISTINCT rema.recipe_id
                FROM rrs_RecipeMaintainer as rema
                INNER JOIN rrs_maintainer AS ma
                ON rema.maintainer_id = ma.id
                WHERE rema.history_id = %s AND ma.name = %s;
                """, [date_id, maintainer])

        for re in cur.fetchall():
            recipes.append(re[0])
        return recipes

    @staticmethod
    def get_reup_by_recipes_and_date(recipes_id, date_id=None):
        stats = []
        recipes = str(recipes_id).strip('[]')

        if date_id:
            qry = """SELECT recipe_id, status, no_update_reason, version
                    FROM rrs_RecipeUpstream"""
            qry += "\nWHERE history_id = '%s' AND" % str(date_id)
            qry += "\nrecipe_id IN (%s)\n" % recipes
            cur = connection.cursor()
            cur.execute(qry)
            stats = Raw.dictfetchall(cur)

        return stats

    @staticmethod
    def get_ma_by_recipes_and_date(recipes_id, date_id=None):
        stats = []
        recipes = str(recipes_id).strip('[]')

        if date_id:
            qry = """SELECT rema.recipe_id, ma.name
                    FROM rrs_RecipeMaintainer AS rema
                    INNER JOIN rrs_Maintainer AS ma
                    ON rema.maintainer_id = ma.id"""
            qry += "\nWHERE rema.history_id = '%s' AND" % str(date_id)
            qry += "\nrema.recipe_id IN (%s)\n" % recipes
            cur = connection.cursor()
            cur.execute(qry)
            stats = Raw.dictfetchall(cur)

        return stats

    @staticmethod
    def get_re_all():
        cur = connection.cursor()
        cur.execute("""SELECT id, pn, pv, summary
                FROM layerindex_recipe""")
        return Raw.dictfetchall(cur)

    @staticmethod
    def get_reupg_by_date(date):
        cur = connection.cursor()
        cur.execute("""SELECT re.id, re.pn, re.summary, te.version, rownum FROM (
                    SELECT recipe_id, version, commit_date,
                    ROW_NUMBER() OVER(
                        PARTITION BY recipe_id
                        ORDER BY commit_date DESC
                    ) AS rownum
                    FROM rrs_RecipeUpgrade
                    WHERE commit_date <= %s) AS te
                INNER JOIN layerindex_Recipe AS re
                ON te.recipe_id = re.id
                WHERE rownum = 1
                ORDER BY re.pn;
                """, [date])
        return Raw.dictfetchall(cur)

    @staticmethod
    def get_reup_by_last_updated(date):
        cur = connection.cursor()
        cur.execute("""SELECT te.recipe_id, te.status, te.date, te.rownum FROM(
                    SELECT  recipe_id, status, date, ROW_NUMBER() OVER(
                        PARTITION BY recipe_id
                        ORDER BY date DESC
                    ) AS rownum
                    FROM rrs_RecipeUpstream
                    WHERE status = 'Y'
                    AND date <= %s) AS te
            WHERE te.rownum = 1;
            """, [date])
        return Raw.dictfetchall(cur)

    @staticmethod
    def dictfetchall(cursor):
        "Returns all rows from a cursor as a dict"
        desc = cursor.description
        return [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
        ]
