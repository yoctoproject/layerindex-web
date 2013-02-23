# layerindex-web - model definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.db import models
from datetime import datetime
from django.contrib.auth.models import User
import os.path

class LayerItem(models.Model):
    LAYER_STATUS_CHOICES = (
        ('N', 'New'),
        ('P', 'Published'),
    )
    LAYER_TYPE_CHOICES = (
        ('A', 'Base'),
        ('B', 'BSP'),
        ('S', 'Software'),
        ('D', 'Distribution'),
        ('M', 'Miscellaneous'),
    )
    name = models.CharField('Layer name', max_length=40, unique=True)
    created_date = models.DateTimeField('Created')
    status = models.CharField(max_length=1, choices=LAYER_STATUS_CHOICES, default='N')
    layer_type = models.CharField(max_length=1, choices=LAYER_TYPE_CHOICES)
    summary = models.CharField(max_length=200)
    description = models.TextField()
    vcs_last_fetch = models.DateTimeField('Last successful fetch', blank=True, null=True)
    vcs_last_rev = models.CharField('Last revision fetched', max_length=80, blank=True)
    vcs_last_commit = models.DateTimeField('Last commit date', blank=True, null=True)
    vcs_subdir = models.CharField('Repository subdirectory', max_length=40, blank=True)
    vcs_url = models.CharField('Repository URL', max_length=200)
    vcs_web_url = models.URLField('Repository web interface URL', blank=True)
    vcs_web_tree_base_url = models.CharField('Repository web interface tree base URL', max_length=200, blank=True)
    vcs_web_file_base_url = models.CharField('Repository web interface file base URL', max_length=200, blank=True)
    usage_url = models.URLField('Usage web page URL', blank=True)

    class Meta:
        verbose_name = "Layer"
        permissions = (
            ("publish_layer", "Can publish layers"),
        )

    def change_status(self, newstatus, username):
        self.status = newstatus

    def _handle_url_path(self, base_url, path):
        if base_url:
            if self.vcs_subdir:
                extra_path = self.vcs_subdir + '/' + path
            else:
                extra_path = path
            if '%path%' in base_url:
                if extra_path:
                    url = re.sub(r'\[([^\]]*%path%[^\]]*)\]', '\\1', base_url)
                    return url.replace('%path%', extra_path)
                else:
                    url = re.sub(r'\[([^\]]*%path%[^\]]*)\]', '', base_url)
                    return url
            else:
                return base_url + extra_path
        return None

    def tree_url(self, path = ''):
        return self._handle_url_path(self.vcs_web_tree_base_url, path)

    def file_url(self, path = ''):
        return self._handle_url_path(self.vcs_web_file_base_url, path)

    def sorted_recipes(self):
        return self.recipe_set.order_by('filename')

    def active_maintainers(self):
        return self.layermaintainer_set.filter(status='A')

    def __unicode__(self):
        return self.name


class LayerMaintainer(models.Model):
    MAINTAINER_STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    layer = models.ForeignKey(LayerItem)
    name = models.CharField(max_length=50)
    email = models.CharField(max_length=255)
    responsibility = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=1, choices=MAINTAINER_STATUS_CHOICES, default='A')

    def __unicode__(self):
        respstr = ""
        if self.responsibility:
            respstr = " (%s)" % self.responsibility
        return "%s: %s <%s>%s" % (self.layer.name, self.name, self.email, respstr)


class LayerDependency(models.Model):
    layer = models.ForeignKey(LayerItem, related_name='dependencies_set')
    dependency = models.ForeignKey(LayerItem, related_name='dependents_set')

    class Meta:
        verbose_name_plural = "Layer dependencies"

    def __unicode__(self):
        return "%s depends on %s" % (self.layer.name, self.dependency.name)


class LayerNote(models.Model):
    layer = models.ForeignKey(LayerItem)
    text = models.TextField()

    def __unicode__(self):
        return self.text


class Recipe(models.Model):
    layer = models.ForeignKey(LayerItem)
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=255, blank=True)
    pn = models.CharField(max_length=40, blank=True)
    pv = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    license = models.CharField(max_length=100, blank=True)
    homepage = models.URLField(blank=True)

    def vcs_web_url(self):
        url = self.layer.file_url(os.path.join(self.filepath, self.filename))
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
