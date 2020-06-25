# layerindex-web - model definitions
#
# Copyright (C) 2013-2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.db import models
from datetime import datetime
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.validators import URLValidator
from django.db.models.signals import pre_save
from django.dispatch import receiver
from collections import namedtuple
import os.path
import re
import posixpath
import codecs

from . import utils


logger = utils.logger_create('LayerIndexModels')


@receiver(pre_save)
def truncate_charfield_values(sender, instance, *args, **kwargs):
    # Instead of leaving this up to the database, check and handle it
    # ourselves to avoid nasty exceptions; as a bonus we won't miss when
    # the max length is too short with databases that don't enforce
    # the limits (e.g. sqlite)
    for field in instance._meta.get_fields():
        if isinstance(field, models.CharField):
            value = getattr(instance, field.name)
            if value and len(value) > field.max_length:
                logger.warning('%s.%s: %s: length %s exceeds maximum (%s), truncating' % (instance.__class__.__name__, field.name, str(instance), len(value), field.max_length))
                setattr(instance, field.name, value[:field.max_length])


class PythonEnvironment(models.Model):
    name = models.CharField(max_length=50)
    python_command = models.CharField(max_length=255, default='python')
    virtualenv_path = models.CharField(max_length=255, blank=True)

    def get_command(self):
        if self.virtualenv_path:
            cmd = '. %s/bin/activate; %s' % (self.virtualenv_path, self.python_command)
        else:
            cmd = self.python_command
        return cmd

    @staticmethod
    def get_default_python2_environment():
        for env in PythonEnvironment.objects.all().order_by('id'):
            if env.name.replace(' ', '').lower().startswith(('python2', 'py2')):
                return env
        return None

    @staticmethod
    def get_default_python3_environment():
        for env in PythonEnvironment.objects.all().order_by('id'):
            if env.name.replace(' ', '').lower().startswith(('python3', 'py3')):
                return env
        return None

    def __str__(self):
        return self.name


class Branch(models.Model):
    name = models.CharField('Branch name', max_length=50)
    bitbake_branch = models.CharField(max_length=50)
    short_description = models.CharField(max_length=50, blank=True)
    sort_priority = models.IntegerField(blank=True, null=True)
    updates_enabled = models.BooleanField('Enable updates', default=True, help_text='Enable automatically updating layer metadata for this branch via the update script')
    comparison = models.BooleanField('Comparison', default=False, help_text='If enabled, branch is for comparison purposes only and will appear separately')
    update_environment = models.ForeignKey(PythonEnvironment, blank=True, null=True, on_delete=models.SET_NULL)
    hidden = models.BooleanField('Hidden', default=False, help_text='Hide from normal selections')

    updated = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Branches"
        ordering = ['sort_priority']

    def __str__(self):
        if self.comparison and self.short_description:
            return self.short_description
        elif self.short_description:
            return '%s (%s)' % (self.name, self.short_description)
        else:
            return self.name


class Update(models.Model):
    started = models.DateTimeField()
    finished = models.DateTimeField(blank=True, null=True)
    log = models.TextField(blank=True)
    reload = models.BooleanField('Reloaded', default=False, help_text='Was this update a reload?')
    task_id = models.CharField(max_length=50, blank=True, db_index=True)
    triggered_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    retcode = models.IntegerField(default=0)

    def error_count(self):
        sums = self.layerupdate_set.aggregate(errors=models.Sum('errors'))
        return (sums['errors'] or 0) + self.log.count('ERROR:')

    def warning_count(self):
        sums = self.layerupdate_set.aggregate(warnings=models.Sum('warnings'))
        return (sums['warnings'] or 0) + self.log.count('WARNING:')

    def __str__(self):
        return '%s' % self.started


class LayerItem(models.Model):
    LAYER_STATUS_CHOICES = (
        ('N', 'New'),
        ('P', 'Published'),
        ('X', 'No update'),
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
    vcs_web_commit_url = models.CharField('Repository web interface commit URL', max_length=255, blank=True, help_text='Base URL for the web interface for viewing a single commit within the repository, if any')
    usage_url = models.CharField('Usage web page URL', max_length=255, blank=True, help_text='URL of a web page with more information about the layer and how to use it, if any (or path to file within repository)')
    mailing_list_url = models.URLField('Mailing list URL', blank=True, help_text='URL of the info page for a mailing list for discussing the layer, if any')
    index_preference = models.IntegerField('Preference', default=0, help_text='Number used to find preferred recipes in recipe search results (higher number is greater preference)')
    comparison = models.BooleanField('Comparison', default=False, help_text='Is this a comparison layer?')
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Layer"
        permissions = (
            ("publish_layer", "Can publish layers"),
        )

    def change_status(self, newstatus, username):
        self.status = newstatus

    def get_layerbranch(self, branchname):
        if branchname:
            res = list(self.layerbranch_set.filter(branch__name=branchname)[:1])
        else:
            res = list(self.layerbranch_set.all()[:1])
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
        if user.is_authenticated:
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
        return reverse('layer_item', args=('master',self.name));

    def __str__(self):
        return self.name


class LayerRecipeExtraURL(models.Model):
    layer = models.ForeignKey(LayerItem, on_delete=models.CASCADE)
    name = models.CharField(max_length=50, help_text='Name to display for link')
    url = models.CharField('URL', max_length=255, help_text='Template for URL to link to (macros: %pn% %pv% %branch% %actual_branch%)')

    class Meta:
        verbose_name = "Layer Recipe Extra URL"

    def render_url(self, recipe):
        url = self.url
        url = url.replace('%pn%', recipe.pn)
        url = url.replace('%pv%', recipe.pv)
        url = url.replace('%branch%', recipe.layerbranch.branch.name)
        url = url.replace('%actual_branch%', recipe.layerbranch.get_checkout_branch())
        return url

    def __str__(self):
        return '%s - %s' % (self.layer.name, self.name)


class YPCompatibleVersion(models.Model):
    name = models.CharField('Yocto Project Version', max_length=25, unique=True, help_text='Name of this Yocto Project compatible version (e.g. "2.0")')
    description = models.TextField(blank=True)
    image_url = models.CharField('Image URL', max_length=300, blank=True)
    link_url = models.CharField('Link URL', max_length=100, blank=True)

    class Meta:
        verbose_name = 'Yocto Project Compatible version'
        ordering = ('name',)

    def __str__(self):
        return self.name

class LayerBranch(models.Model):
    layer = models.ForeignKey(LayerItem, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    collection = models.CharField('Layer Collection', max_length=40, null=True, blank=True, help_text='Name of the collection that the layer provides for the purpose of expressing dependencies (as specified in BBFILE_COLLECTIONS). Can only contain letters, numbers and dashes.')
    version = models.CharField('Layer Version', max_length=10, null=True, blank=True, help_text='The layer version for this particular branch.')
    vcs_subdir = models.CharField('Repository subdirectory', max_length=40, blank=True, help_text='Subdirectory within the repository where the layer is located, if not in the root (usually only used if the repository contains more than one layer)')
    vcs_last_fetch = models.DateTimeField('Last successful fetch', blank=True, null=True)
    vcs_last_rev = models.CharField('Last revision fetched', max_length=80, blank=True)
    vcs_last_commit = models.DateTimeField('Last commit date', blank=True, null=True)
    actual_branch = models.CharField('Actual Branch', max_length=80, blank=True, help_text='Name of the actual branch in the repository matching the core branch')
    yp_compatible_version = models.ForeignKey(YPCompatibleVersion, verbose_name='Yocto Project Compatible version', null=True, blank=True, on_delete=models.SET_NULL, help_text='Which version of the Yocto Project Compatible program has this layer been approved for for?')
    local_path = models.CharField(max_length=255, blank=True, help_text='Local subdirectory where layer data can be found')

    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Layer branches"
        permissions = (
            ("set_yp_compatibility", "Can set YP compatibility"),
        )

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
            if self.actual_branch:
                branchname = self.actual_branch
            else:
                branchname = self.branch.name
            url = base_url.replace('%branch%', branchname)
            if path:
                splitpath = path.split('/')
                for match in re.findall('(%pathelement\[([0-9]*)(:[0-9]*)?\]%)', url):
                    if match[1] == '':
                        start = None
                    else:
                        start = int(match[1])
                    if ':' in match[2]:
                        stopstr = match[2][1:]
                        if stopstr == '':
                            stop = None
                        else:
                            stop = int(stopstr)
                        url = url.replace(match[0], '/'.join(splitpath[start:stop]))
                    else:
                        url = url.replace(match[0], splitpath[start])

            # If there's a % in the path (e.g. a wildcard bbappend) we need to encode it
            if extra_path:
                extra_path = extra_path.replace('%', '%25')

            if '%path%' in base_url or '%pathelement[' in base_url:
                if extra_path:
                    url = re.sub(r'\[([^\]]*%path%[^\]]*)\]', '\\1', url)
                else:
                    url = re.sub(r'\[([^\]]*%path%[^\]]*)\]', '', url)
                return url.replace('%path%', extra_path)
            else:
                return url + extra_path
        return None

    def tree_url(self, path = ''):
        return self._handle_url_path(self.layer.vcs_web_tree_base_url, path)

    def file_url(self, path = ''):
        return self._handle_url_path(self.layer.vcs_web_file_base_url, path)

    def commit_url(self, commit_hash):
        url = self.layer.vcs_web_commit_url
        url = url.replace('%hash%', commit_hash)
        url = url.replace('%branch%', self.get_checkout_branch())
        return url

    def test_tree_url(self):
        return self.tree_url('conf')

    def test_file_url(self):
        return self.file_url('conf/layer.conf')

    def get_checkout_branch(self):
        """Get the branch that we actually need to check out in the repo"""
        if self.actual_branch:
            return self.actual_branch
        else:
            return self.branch.name

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

    def __str__(self):
        return "%s: %s" % (self.layer.name, self.branch.name)


    def get_required(self):
        return self.dependencies_set.filter(required=True)

    def get_recommends(self):
        return self.dependencies_set.filter(required=False)

    def get_recursive_dependencies(self, required=True, include_self=False):
        deplist = []
        def recurse_deps(layerbranch):
            deplist.append(layerbranch)
            if required:
                dep_set = layerbranch.dependencies_set.filter(required=True)
            else:
                dep_set = layerbranch.dependencies_set.all()
            for dep in dep_set:
                deplayerbranch = dep.dependency.get_layerbranch(layerbranch.branch.name)
                if deplayerbranch and deplayerbranch not in deplist:
                    recurse_deps(deplayerbranch)
        recurse_deps(self)
        if include_self:
            return deplist
        else:
            return deplist[1:]

class LayerMaintainer(models.Model):
    MAINTAINER_STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    responsibility = models.CharField(max_length=200, blank=True, help_text='Specific area(s) this maintainer is responsible for, if not the entire layer')
    status = models.CharField(max_length=1, choices=MAINTAINER_STATUS_CHOICES, default='A')

    def __str__(self):
        respstr = ""
        if self.responsibility:
            respstr = " (%s)" % self.responsibility
        return "%s: %s <%s>%s" % (self.layerbranch, self.name, self.email, respstr)


class LayerDependency(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, related_name='dependencies_set', on_delete=models.CASCADE)
    dependency = models.ForeignKey(LayerItem, related_name='dependents_set', on_delete=models.CASCADE)
    required = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Layer dependencies"

    def __str__(self):
        return "%s depends on %s" % (self.layerbranch.layer.name, self.dependency.name)


class LayerNote(models.Model):
    layer = models.ForeignKey(LayerItem, on_delete=models.CASCADE)
    text = models.TextField()

    def __str__(self):
        return "%s: %s" % (self.layer.name, self.text)


class LayerUpdate(models.Model):
    layer = models.ForeignKey(LayerItem, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    update = models.ForeignKey(Update, on_delete=models.CASCADE)
    started = models.DateTimeField()
    finished = models.DateTimeField(blank=True, null=True)
    errors = models.IntegerField(default=0)
    warnings = models.IntegerField(default=0)
    vcs_before_rev = models.CharField('Revision before', max_length=80, blank=True)
    vcs_after_rev = models.CharField('Revision after', max_length=80, blank=True)
    log = models.TextField(blank=True)
    retcode = models.IntegerField(default=0)

    def layerbranch_exists(self):
        """Helper function for linking"""
        return LayerBranch.objects.filter(layer=self.layer, branch=self.branch).exists()

    def vcs_before_commit_url(self):
        if self.vcs_before_rev:
            layerbranch = LayerBranch.objects.filter(layer=self.layer, branch=self.branch).first()
            if layerbranch:
                return layerbranch.commit_url(self.vcs_before_rev)
        return None

    def vcs_after_commit_url(self):
        if self.vcs_after_rev:
            layerbranch = LayerBranch.objects.filter(layer=self.layer, branch=self.branch).first()
            if layerbranch:
                return layerbranch.commit_url(self.vcs_after_rev)
        return None

    def save(self):
        warnings = 0
        errors = 0
        for line in self.log.splitlines():
            if line.startswith('WARNING:'):
                warnings += 1
            elif line.startswith('ERROR:'):
                errors += 1
        self.warnings = warnings
        self.errors = errors
        super(LayerUpdate, self).save()

    def __str__(self):
        return "%s: %s: %s" % (self.layer.name, self.branch.name, self.started)


class Recipe(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=255, blank=True)
    pn = models.CharField(max_length=100, blank=True)
    pv = models.CharField(max_length=100, blank=True)
    pr = models.CharField(max_length=100, blank=True)
    pe = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    license = models.CharField(max_length=2048, blank=True)
    homepage = models.URLField(blank=True)
    bugtracker = models.URLField(blank=True)
    provides = models.CharField(max_length=2048, blank=True)
    bbclassextend = models.CharField(max_length=100, blank=True)
    inherits = models.CharField(max_length=255, blank=True)
    updated = models.DateTimeField(auto_now=True)
    blacklisted = models.CharField(max_length=255, blank=True)
    configopts = models.CharField(max_length=4096, blank=True)
    srcrev = models.CharField(max_length=64, blank=True)

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

    def homepage_url_only(self):
        if '://' in self.homepage:
            return self.homepage
        else:
            return None

    def extra_urls(self):
        ExtraURL = namedtuple('ExtraURL', 'name url')
        for item in self.layerbranch.layer.layerrecipeextraurl_set.all():
            eu = ExtraURL(name=item.name, url=item.render_url(self))
            yield eu

    def adjacent_includes(self):
        """Returns an iterator over any files included by this recipe that are adjacent to the recipe (usually .inc files)"""
        recipepath = os.path.join(self.layerbranch.vcs_subdir, self.filepath)
        if not recipepath.endswith('/'):
            recipepath += '/'
        IncludeFile = namedtuple('IncludeFile', 'filepath vcs_web_url')
        for rfd in self.recipefiledependency_set.all():
            if rfd.path.startswith(recipepath) and not os.path.basename(rfd.path) == self.filename:
                ifile = IncludeFile(filepath=rfd.layer_path(), vcs_web_url=rfd.vcs_web_url())
                yield ifile

    def comparison_recipes(self):
        return ClassicRecipe.objects.filter(cover_layerbranch=self.layerbranch).filter(cover_pn=self.pn)

    def __str__(self):
        return os.path.join(self.filepath, self.filename)


class Source(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    url = models.CharField(max_length=255)
    sha256sum = models.CharField(max_length=64, blank=True)

    def web_url(self):
        def drop_dotgit(url):
            if url.endswith('.git'):
                url = url[:-4]
            return url
        if self.url and self.url.startswith(('http', 'ftp')):
            return self.url
        elif self.url.startswith('git://github.com'):
            return drop_dotgit('https' + self.url[3:])
        elif self.url.startswith('git://git.yoctoproject.org'):
            return drop_dotgit('https://git.yoctoproject.org/cgit/cgit.cgi' + self.url[26:])
        elif self.url.startswith('git://git.kernel.org'):
            return 'https' + self.url[3:]
        return None

    def __str__(self):
        return '%s - %s - %s' % (self.recipe.layerbranch, self.recipe.pn, self.url)

patch_status_re = re.compile(r"^[\t ]*(Upstream[-_ ]Status:?)[\t ]*(\w+)([\t ]+.*)?", re.IGNORECASE | re.MULTILINE)

class Patch(models.Model):
    PATCH_STATUS_CHOICES = [
        ('U', 'Unknown'),
        ('A', 'Accepted'),
        ('P', 'Pending'),
        ('I', 'Inappropriate'),
        ('B', 'Backport'),
        ('S', 'Submitted'),
        ('D', 'Denied'),
        ]
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    path = models.CharField(max_length=255)
    src_path = models.CharField(max_length=255)
    status = models.CharField(max_length=1, choices=PATCH_STATUS_CHOICES, default='U')
    status_extra = models.CharField(max_length=255, blank=True)
    apply_order = models.IntegerField(blank=True, null=True)
    applied = models.BooleanField(default=True)
    striplevel = models.IntegerField(default=1)

    class Meta:
        verbose_name_plural = 'Patches'
        ordering = ['recipe', 'apply_order']

    def vcs_web_url(self):
        url = self.recipe.layerbranch.file_url(self.path)
        return url or ''

    def read_status_from_file(self, patchfn, logger=None):
        for encoding in ['utf-8', 'latin-1']:
            try:
                with codecs.open(patchfn, 'r', encoding=encoding) as f:
                    for line in f:
                        line = line.rstrip()
                        if line.startswith('Index: ') or line.startswith('diff -') or line.startswith('+++ '):
                            break
                        res = patch_status_re.match(line)
                        if res:
                            status = res.group(2).lower()
                            for key, value in dict(Patch.PATCH_STATUS_CHOICES).items():
                                if status == value.lower():
                                    self.status = key
                                    if res.group(3):
                                        self.status_extra = res.group(3).strip()
                                    break
                            else:
                                if logger:
                                    logger.warn('Invalid upstream status in %s: %s' % (patchfn, line))
            except UnicodeDecodeError:
                continue
            break
        else:
            if logger:
                logger.error('Unable to find suitable encoding to read patch %s' % patchfn)

    def __str__(self):
        return "%s - %s" % (self.recipe, self.src_path)


class PackageConfig(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    feature = models.CharField(max_length=255)
    with_option = models.CharField(max_length=255, blank=True)
    without_option = models.CharField(max_length=255, blank=True)
    build_deps = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "%s - %s" % (self.recipe, self.feature)

    def get_deps_list(self):
        return self.build_deps.split()

class StaticBuildDep(models.Model):
    recipes = models.ManyToManyField(Recipe)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class DynamicBuildDep(models.Model):
    package_configs = models.ManyToManyField(PackageConfig)
    recipes = models.ManyToManyField(Recipe)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class RecipeFileDependency(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    layerbranch = models.ForeignKey(LayerBranch, related_name='+', on_delete=models.CASCADE)
    path = models.CharField(max_length=255, db_index=True)

    class Meta:
        verbose_name_plural = "Recipe file dependencies"

    def layer_path(self):
        return os.path.relpath(self.path, self.layerbranch.vcs_subdir)

    def vcs_web_url(self):
        url = self.layerbranch.file_url(self.layer_path())
        return url or ''

    def __str__(self):
        return '%s' % self.path


class ClassicRecipe(Recipe):
    COVER_STATUS_CHOICES = [
        ('U', 'Unknown'),
        ('N', 'Not available'),
        ('R', 'Replaced'),
        ('P', 'Provided (BBCLASSEXTEND)'),
        ('C', 'Provided (PACKAGECONFIG)'),
        ('S', 'Distro-specific'),
        ('O', 'Obsolete'),
        ('E', 'Equivalent functionality'),
        ('D', 'Direct match'),
    ]
    cover_layerbranch = models.ForeignKey(LayerBranch, verbose_name='Covering layer', blank=True, null=True, limit_choices_to = {'branch__name': 'master'}, on_delete=models.SET_NULL)
    cover_pn = models.CharField('Covering recipe', max_length=100, blank=True)
    cover_status = models.CharField(max_length=1, choices=COVER_STATUS_CHOICES, default='U')
    cover_verified = models.BooleanField(default=False)
    cover_comment = models.TextField(blank=True)
    classic_category = models.CharField('OE-Classic Category', max_length=100, blank=True)
    deleted = models.BooleanField(default=False)
    needs_attention = models.BooleanField(default=False)

    class Meta:
        permissions = (
            ("edit_classic", "Can edit OE-Classic recipes"),
            ("update_comparison_branch", "Can update comparison branches"),
        )

    def get_cover_desc(self):
        desc = self.get_cover_status_display()
        if self.cover_layerbranch:
            cover_layer = self.cover_layerbranch.layer.name
        else:
            cover_layer = '(unknown layer)'
        if self.cover_status == 'D':
            desc = 'Direct match exists in %s' % cover_layer
        elif self.cover_pn:
            if self.cover_status == 'R':
                desc = 'Replaced by %s in %s' % (self.cover_pn, cover_layer)
            elif self.cover_status == 'P':
                desc = 'Provided by %s in %s (BBCLASSEXTEND)' % (self.cover_pn, cover_layer)
            elif self.cover_status == 'C':
                desc = 'Provided by %s in %s (as a PACKAGECONFIG option)' % (self.cover_pn, cover_layer)
            elif self.cover_status == 'E':
                desc = 'Equivalent functionality provided by %s in %s' % (self.cover_pn, cover_layer)
        if self.cover_comment:
            if self.cover_comment[0] == '(':
                desc = "%s %s" % (desc, self.cover_comment)
            else:
                desc = "%s - %s" % (desc, self.cover_comment)
        return desc

    def get_cover_recipe(self):
        if self.cover_layerbranch and self.cover_pn:
            return Recipe.objects.filter(layerbranch=self.cover_layerbranch).filter(pn=self.cover_pn).first()
        else:
            return None


class ComparisonRecipeUpdate(models.Model):
    update = models.ForeignKey(Update, on_delete=models.CASCADE)
    recipe = models.ForeignKey(ClassicRecipe, on_delete=models.CASCADE)
    meta_updated = models.BooleanField(default=False)
    link_updated = models.BooleanField(default=False)

    def __str__(self):
        return '%s - %s' % (self.update, self.recipe)


class Machine(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    updated = models.DateTimeField(auto_now=True)

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join('conf/machine/%s.conf' % self.name))
        return url or ''

    def __str__(self):
        return '%s (%s)' % (self.name, self.layerbranch.layer.name)

class Distro(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    updated = models.DateTimeField(auto_now=True)

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join('conf/distro/%s.conf' % self.name))
        return url or ''

    def __str__(self):
        return '%s (%s)' % (self.name, self.layerbranch.layer.name)


class BBAppend(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Append"

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join(self.filepath, self.filename))
        return url or ''

    def matches_recipe(self, recipe):
        recipename = recipe.filename[:-3]
        appendname = self.filename[:-9]
        if recipename == appendname:
            return True
        elif '%' in appendname:
            import fnmatch
            return fnmatch.fnmatch(recipename, appendname.replace('%', '*'))
        return False

    def __str__(self):
        return '%s: %s' % (self.layerbranch, os.path.join(self.filepath, self.filename))


class BBClass(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"

    def vcs_web_url(self):
        url = self.layerbranch.file_url(os.path.join('classes', "%s.bbclass" % self.name))
        return url or ''

    def __str__(self):
        return '%s (%s)' % (self.name, self.layerbranch.layer.name)


class IncFile(models.Model):
    layerbranch = models.ForeignKey(LayerBranch, on_delete=models.CASCADE)
    path = models.CharField(max_length=255)

    def vcs_web_url(self):
        url = self.layerbranch.file_url(self.path)
        return url or ''

    def __str__(self):
        return '%s (%s)' % (self.path, self.layerbranch.layer.name)


class RecipeChangeset(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
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

    changeset = models.ForeignKey(RecipeChangeset, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, related_name='+', on_delete=models.CASCADE)
    summary = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    license = models.CharField(max_length=100, blank=True)
    homepage = models.URLField("Homepage URL", blank=True)
    bugtracker = models.URLField("Bug tracker URL", blank=True)

    def changed_fields(self, mapped = False):
        res = {}
        for fieldname in self.RECIPE_VARIABLE_MAP:
            value = getattr(self, fieldname)
            origvalue = getattr(self.recipe, fieldname)
            if value != origvalue:
                if mapped:
                    res[self.RECIPE_VARIABLE_MAP[fieldname]] = value
                else:
                    res[fieldname] = value
        return res

    def reset_fields(self):
        for fieldname in self.RECIPE_VARIABLE_MAP:
            setattr(self, fieldname, getattr(self.recipe, fieldname))

class SiteNotice(models.Model):
    NOTICE_LEVEL_CHOICES = [
        ('I', 'Info'),
        ('S', 'Success'),
        ('W', 'Warning'),
        ('E', 'Error'),
    ]
    text = models.TextField(help_text='Text to show in the notice. A limited subset of HTML is supported for formatting.')
    level = models.CharField(max_length=1, choices=NOTICE_LEVEL_CHOICES, default='I', help_text='Level of notice to display')
    disabled = models.BooleanField('Disabled', default=False, help_text='Use to temporarily disable this notice')
    expires = models.DateTimeField(blank=True, null=True, help_text='Optional date/time when this notice will stop showing')

    def __str__(self):
        prefix = ''
        if self.expires and datetime.now() >= self.expires:
            prefix = '[expired] '
        elif self.disabled:
            prefix = '[disabled] '
        return '%s%s' % (prefix, self.text)

    def text_sanitised(self):
        return utils.sanitise_html(self.text)


class SecurityQuestion(models.Model):
    question = models.CharField(max_length = 250, null=False)

    def __str__(self):
        return '%s' % (self.question)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    answer_attempts = models.IntegerField(default=0)

    def __str__(self):
        return '%s' % (self.user)


class SecurityQuestionAnswer(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    security_question = models.ForeignKey(SecurityQuestion, on_delete=models.CASCADE)
    answer = models.CharField(max_length = 250, null=False)

    def __str__(self):
        return '%s - %s' % (self.user, self.security_question)


class PatchDisposition(models.Model):
    PATCH_DISPOSITION_CHOICES = (
        ('A', 'Apply'),
        ('R', 'Further review'),
        ('E', 'Existing'),
        ('N', 'Not needed'),
        ('V', 'Different version'),
        ('I', 'Invalid'),
    )
    patch = models.OneToOneField(Patch, on_delete=models.CASCADE)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    disposition = models.CharField(max_length=1, choices=PATCH_DISPOSITION_CHOICES, default='A')
    comment = models.TextField(blank=True)

    class Meta:
        permissions = (
            ("patch_disposition", "Can disposition patches"),
        )

    def __str__(self):
        return '%s - %s' % (self.patch, self.get_disposition_display())


class ExtendedProvide(models.Model):
    recipes = models.ManyToManyField(Recipe)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
