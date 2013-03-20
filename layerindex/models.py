# layerindex-web - model definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.db import models
from datetime import datetime
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.validators import URLValidator
import os.path
import re
import posixpath


class Branch(models.Model):
    name = models.CharField(max_length=50)
    bitbake_branch = models.CharField(max_length=50)
    short_description = models.CharField(max_length=50, blank=True)
    sort_priority = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Branches"

    def __unicode__(self):
        return self.name


class LayerItem(models.Model):
    LAYER_STATUS_CHOICES = (
        ('N', 'New'),
        ('P', 'Published'),
    )
    LAYER_TYPE_CHOICES = (
        ('A', 'Base'),
        ('B', 'Machine (BSP)'),
        ('S', 'Software'),
        ('D', 'Distribution'),
        ('M', 'Miscellaneous'),
    )
    name = models.CharField('Layer name', max_length=40, unique=True, help_text='Name of the layer - must be unique and can only contain letters, numbers and dashes')
    status = models.CharField(max_length=1, choices=LAYER_STATUS_CHOICES, default='N')
    layer_type = models.CharField(max_length=1, choices=LAYER_TYPE_CHOICES)
    summary = models.CharField(max_length=200, help_text='One-line description of the layer')
    description = models.TextField()
    vcs_url = models.CharField('Repository URL', max_length=255, help_text='Fetch/clone URL of the repository')
    vcs_web_url = models.URLField('Repository web interface URL', blank=True, help_text='URL of the web interface for browsing the repository, if any')
    vcs_web_tree_base_url = models.CharField('Repository web interface tree base URL', max_length=255, blank=True, help_text='Base URL for the web interface for browsing directories within the repository, if any')
    vcs_web_file_base_url = models.CharField('Repository web interface file base URL', max_length=255, blank=True, help_text='Base URL for the web interface for viewing files (blobs) within the repository, if any')
    usage_url = models.CharField('Usage web page URL', max_length=255, blank=True, help_text='URL of a web page with more information about the layer and how to use it, if any (or path to file within repository)')
    mailing_list_url = models.URLField('Mailing list URL', blank=True, help_text='URL of the info page for a mailing list for discussing the layer, if any')
    index_preference = models.IntegerField('Preference', default=0, help_text='Number used to find preferred recipes in recipe search results (higher number is greater preference)')

    class Meta:
        verbose_name = "Layer"
        permissions = (
            ("publish_layer", "Can publish layers"),
        )

    def change_status(self, newstatus, username):
        self.status = newstatus

    def get_layerbranch(self, branchname):
        res = list(self.layerbranch_set.filter(branch__name=branchname)[:1])
        if res:
            return res[0]
        return None

    def active_maintainers(self):
        matches = None
        for layerbranch in self.layerbranch_set.all():
            branchmatches = layerbranch.layermaintainer_set.filter(status='A')
            if matches:
                matches |= branchmatches
            else:
                matches = branchmatches
        return matches

    def user_can_edit(self, user):
        if user.is_authenticated():
            user_email = user.email.strip().lower()
            for maintainer in self.active_maintainers():
                if maintainer.email.strip().lower() == user_email:
                    return True
        return False

    def get_fetch_dir(self):
        fetch_dir = ""
        for c in self.vcs_url:
            if c in '/ .=+?:':
                fetch_dir += "_"
            else:
                fetch_dir += c
        return fetch_dir

    def get_absolute_url(self):
        return reverse('layer_item', args=(self.name,));

    def __unicode__(self):
        return self.name


class LayerBranch(models.Model):
    layer = models.ForeignKey(LayerItem)
    branch = models.ForeignKey(Branch)
    vcs_subdir = models.CharField('Repository subdirectory', max_length=40, blank=True, help_text='Subdirectory within the repository where the layer is located, if not in the root (usually only used if the repository contains more than one layer)')
    vcs_last_fetch = models.DateTimeField('Last successful fetch', blank=True, null=True)
    vcs_last_rev = models.CharField('Last revision fetched', max_length=80, blank=True)
    vcs_last_commit = models.DateTimeField('Last commit date', blank=True, null=True)
    actual_branch = models.CharField('Actual Branch', max_length=80, blank=True, help_text='Name of the actual branch in the repository matching the core branch')

    class Meta:
        verbose_name_plural = "Layer branches"

    def sorted_recipes(self):
        return self.recipe_set.order_by('pn', '-pv')

    def active_maintainers(self):
        return self.layermaintainer_set.filter(status='A')

    def _handle_url_path(self, base_url, path):
        if base_url:
            if self.vcs_subdir:
                if path:
                    extra_path = self.vcs_subdir + '/' + path
                    # Normalise out ../ in path for usage URL
                    extra_path = posixpath.normpath(extra_path)
                    # Minor workaround to handle case where subdirectory has been added between branches
                    # (should probably support usage URL per branch to handle this... sigh...)
                    if extra_path.startswith('../'):
                        extra_path = extra_path[3:]
                else:
                    extra_path = self.vcs_subdir
            else:
                extra_path = path
            url = base_url.replace('%branch%', self.branch.name)
            if '%path%' in base_url:
                if extra_path:
                    url = re.sub(r'\[([^\]]*%path%[^\]]*)\]', '\\1', url)
                    return url.replace('%path%', extra_path)
                else:
                    url = re.sub(r'\[([^\]]*%path%[^\]]*)\]', '', url)
                    return url
            else:
                return url + extra_path
        return None

    def tree_url(self, path = ''):
        return self._handle_url_path(self.layer.vcs_web_tree_base_url, path)

    def file_url(self, path = ''):
        return self._handle_url_path(self.layer.vcs_web_file_base_url, path)

    def test_tree_url(self):
        return self.tree_url('conf')

    def test_file_url(self):
        return self.file_url('conf/layer.conf')

    def get_usage_url(self):
        usage_url = self.layer.usage_url
        if usage_url.startswith('http'):
            return usage_url
        else:
            url = self.file_url(usage_url)
            if url:
                if '/../' in url:
                    url = resolveComponents(url)
            return url

    def __unicode__(self):
        return "%s: %s" % (self.layer.name, self.branch.name)


class LayerMaintainer(models.Model):
    MAINTAINER_STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    layerbranch = models.ForeignKey(LayerBranch)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    responsibility = models.CharField(max_length=200, blank=True, help_text='Specific area(s) this maintainer is responsible for, if not the entire layer')
    status = models.CharField(max_length=1, choices=MAINTAINER_STATUS_CHOICES, default='A')

    def __unicode__(self):
        respstr = ""
        if self.responsibility:
            respstr = " (%s)" % self.responsibility
        return "%s: %s <%s>%s" % (self.layerbranch.layer.name, self.name, self.email, respstr)


class LayerDependency(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, related_name='dependencies_set')
    dependency = models.ForeignKey(LayerItem, related_name='dependents_set')

    class Meta:
        verbose_name_plural = "Layer dependencies"

    def __unicode__(self):
        return "%s depends on %s" % (self.layerbranch.layer.name, self.dependency.name)


class LayerNote(models.Model):
    layer = models.ForeignKey(LayerItem)
    text = models.TextField()

    def __unicode__(self):
        return "%s: %s" % (self.layer.name, self.text)


class Recipe(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=255, blank=True)
    pn = models.CharField(max_length=100, blank=True)
    pv = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    license = models.CharField(max_length=100, blank=True)
    homepage = models.URLField(blank=True)
    bugtracker = models.URLField(blank=True)
    provides = models.CharField(max_length=255, blank=True)
    bbclassextend = models.CharField(max_length=100, blank=True)

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join(self.filepath, self.filename))
        return url or ''

    def full_path(self):
        return os.path.join(self.filepath, self.filename)

    def short_desc(self):
        if self.summary:
            return self.summary
        else:
            return self.description

    def name(self):
        if self.pn:
            return self.pn
        else:
            return self.filename.split('_')[0]

    def __unicode__(self):
        return os.path.join(self.filepath, self.filename)


class RecipeFileDependency(models.Model):
    recipe = models.ForeignKey(Recipe)
    layerbranch = models.ForeignKey(LayerBranch, related_name='+')
    path = models.CharField(max_length=255, db_index=True)

    class Meta:
        verbose_name_plural = "Recipe file dependencies"

    def __unicode__(self):
        return '%s' % self.path


class Machine(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join('conf/machine/%s.conf' % self.name))
        return url or ''

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.layerbranch.layer.name)


class BBAppend(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Append"

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join(self.filepath, self.filename))
        return url or ''

    def __unicode__(self):
        return os.path.join(self.filepath, self.filename)


class BBClass(models.Model):
    layerbranch = models.ForeignKey(LayerBranch)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join('classes', "%s.bbclass" % self.name))
        return url or ''

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.layerbranch.layer.name)


class RecipeChangeset(models.Model):
    user = models.ForeignKey(User)
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return '%s' % (self.name)


class RecipeChange(models.Model):
    RECIPE_VARIABLE_MAP = {
        'summary': 'SUMMARY',
        'description': 'DESCRIPTION',
        'section': 'SECTION',
        'license': 'LICENSE',
        'homepage': 'HOMEPAGE',
        'bugtracker': 'BUGTRACKER',
    }

    changeset = models.ForeignKey(RecipeChangeset)
    recipe = models.ForeignKey(Recipe, related_name='+')
    summary = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    license = models.CharField(max_length=100, blank=True)
    homepage = models.URLField("Homepage URL", blank=True)
    bugtracker = models.URLField("Bug tracker URL", blank=True)

    def changed_fields(self, mapped = False):
        res = {}
        for field in self._meta.fields:
            if not field.name in ['id', 'changeset', 'recipe']:
                value = getattr(self, field.name)
                if value:
                    if mapped:
                        res[self.RECIPE_VARIABLE_MAP[field.name]] = value
                    else:
                        res[field.name] = value
        return res
