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
    name = models.CharField(max_length=40, unique=True)
    created_date = models.DateTimeField('Created')
    status = models.CharField(max_length=1, choices=LAYER_STATUS_CHOICES, default='N')
    layer_type = models.CharField(max_length=1, choices=LAYER_TYPE_CHOICES, default='M')
    summary = models.CharField(max_length=200)
    description = models.TextField()
    vcs_last_fetch = models.DateTimeField('Last successful fetch', blank=True, null=True)
    vcs_last_rev = models.CharField(max_length=80, blank=True)
    vcs_last_commit = models.DateTimeField('Last commit date', blank=True, null=True)
    vcs_subdir = models.CharField('Repository subdirectory', max_length=40, blank=True)
    vcs_url = models.CharField('Repository URL', max_length=200)
    vcs_web_url = models.URLField('Repository web interface URL', blank=True)
    vcs_web_tree_base_url = models.CharField('Repository web interface tree start URL', max_length=200, blank=True)
    usage_url = models.URLField('Usage web page URL', blank=True)

    class Meta:
        permissions = (
            ("publish_layer", "Can publish layers"),
        )

    def change_status(self, newstatus, username):
        self.status = newstatus

    def tree_url(self):
        if self.vcs_subdir and self.vcs_web_tree_base_url:
            return self.vcs_web_tree_base_url + self.vcs_subdir
        else:
            return self.vcs_web_tree_base_url

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
            respstr = " - %s" % self.responsibility
        return "%s <%s>%s" % (self.name, self.email, respstr)


class LayerDependency(models.Model):
    layer = models.ForeignKey(LayerItem, related_name='dependencies_set')
    dependency = models.ForeignKey(LayerItem, related_name='dependents_set')

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
        return os.path.join(self.layer.tree_url(), self.filepath, self.filename)

    def full_path(self):
        return os.path.join(self.filepath, self.filename)

    def short_desc(self):
        if self.summary:
            return self.summary
        else:
            return self.description

    def __unicode__(self):
        return os.path.join(self.filepath, self.filename)
