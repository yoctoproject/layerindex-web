# layerindex-web - view definitions
#
# Copyright (C) 2013-2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import os
import sys
import re
from datetime import datetime
from itertools import islice
from pkg_resources import parse_version

import reversion
from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission, User
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.urls import resolve, reverse, reverse_lazy
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_list_or_404, get_object_or_404, render
from django.template.loader import get_template
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.base import RedirectView
from django.views.generic.edit import (CreateView, DeleteView, FormView,
                                       UpdateView)
from django_registration.backends.activation.views import RegistrationView
from pkg_resources import parse_version
from reversion.models import Revision

import settings
from layerindex.forms import (AdvancedRecipeSearchForm, BulkChangeEditFormSet,
                              ClassicRecipeForm, ClassicRecipeSearchForm,
                              ComparisonRecipeSelectForm, EditLayerForm,
                              EditNoteForm, EditProfileForm,
                              LayerMaintainerFormSet, RecipeChangesetForm,
                              PatchDispositionForm, PatchDispositionFormSet,
                              BranchComparisonForm, RecipeDependenciesForm)
from layerindex.models import (BBAppend, BBClass, Branch, ClassicRecipe,
                               Distro, DynamicBuildDep, IncFile, LayerBranch,
                               LayerDependency, LayerItem, LayerMaintainer,
                               LayerNote, LayerUpdate, Machine, Patch, Recipe,
                               RecipeChange, RecipeChangeset, Source, StaticBuildDep,
                               Update, SecurityQuestion, SecurityQuestionAnswer,
                               UserProfile, PatchDisposition, ExtendedProvide)


from . import tasks, utils

def edit_layernote_view(request, template_name, slug, pk=None):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if layeritem.comparison:
        raise Http404
    if not (request.user.is_authenticated and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
        raise PermissionDenied
    if pk:
        # Edit mode
        layernote = get_object_or_404(LayerNote, pk=pk)
    else:
        # Add mode
        layernote = LayerNote()
        layernote.layer = layeritem

    if request.method == 'POST':
        form = EditNoteForm(request.POST, instance=layernote)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(layeritem.get_absolute_url())
    else:
        form = EditNoteForm(instance=layernote)

    return render(request, template_name, {
        'form': form,
    })

def delete_layernote_view(request, template_name, slug, pk):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if layeritem.comparison:
        raise Http404
    if not (request.user.is_authenticated and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
        raise PermissionDenied
    layernote = get_object_or_404(LayerNote, pk=pk)
    if request.method == 'POST':
        layernote.delete()
        return HttpResponseRedirect(layeritem.get_absolute_url())
    else:
        return render(request, template_name, {
            'object': layernote,
            'object_type': layernote._meta.verbose_name,
            'cancel_url': layeritem.get_absolute_url()
        })

def delete_layer_view(request, template_name, slug):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if layeritem.comparison:
        raise Http404
    if not (request.user.is_authenticated and request.user.has_perm('layerindex.publish_layer') and layeritem.status == 'N'):
        raise PermissionDenied
    if request.method == 'POST':
        layeritem.delete()
        return HttpResponseRedirect(reverse('layer_list', args=('master',)))
    else:
        return render(request, template_name, {
            'object': layeritem,
            'object_type': layeritem._meta.verbose_name,
            'cancel_url': layeritem.get_absolute_url()
        })

def edit_layer_view(request, template_name, branch='master', slug=None):
    return_url = None
    branchobj = Branch.objects.filter(name=branch)[:1].get()
    if slug:
        # Edit mode
        layeritem = get_object_or_404(LayerItem, name=slug)
        if layeritem.comparison:
            raise Http404
        if not (request.user.is_authenticated and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
            raise PermissionDenied
        layerbranch = get_object_or_404(LayerBranch, layer=layeritem, branch=branchobj)
        old_maintainers = list(layerbranch.layermaintainer_set.values_list('email', flat=True))
        deplistlayers = LayerItem.objects.filter(comparison=False).exclude(id=layeritem.id).order_by('name')
        returnto = request.GET.get('returnto', 'layer_item')
        if returnto:
            if returnto == 'layer_review':
                return_url = reverse_lazy(returnto, args=(layeritem.name,))
            else:
                return_url = reverse_lazy(returnto, args=(branch, layeritem.name))
    else:
        # Submit mode
        layeritem = LayerItem()
        layerbranch = LayerBranch(layer=layeritem, branch=branchobj)
        deplistlayers = LayerItem.objects.filter(comparison=False).order_by('name')

    allow_base_type = request.user.has_perm('layerindex.publish_layer') or layeritem.layer_type == 'A'

    if request.method == 'POST':
        last_vcs_url = layeritem.vcs_url
        form = EditLayerForm(request.user, layerbranch, allow_base_type, request.POST, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(request.POST, instance=layerbranch)
        if form.is_valid() and maintainerformset.is_valid():
            with transaction.atomic():
                reset_last_rev = False
                form.save()
                layerbranch.layer = layeritem
                new_subdir = form.cleaned_data['vcs_subdir']
                if layerbranch.vcs_subdir != new_subdir:
                    layerbranch.vcs_subdir = new_subdir
                    reset_last_rev = True
                layerbranch.save()
                maintainerformset.save()
                if slug:
                    new_deps = form.cleaned_data['deps']
                    existing_deps = [deprec.dependency for deprec in layerbranch.dependencies_set.all()]
                    reset_last_rev = False
                    for dep in new_deps:
                        if dep not in existing_deps:
                            deprec = LayerDependency()
                            deprec.layerbranch = layerbranch
                            deprec.dependency = dep
                            deprec.save()
                            reset_last_rev = True
                    for dep in existing_deps:
                        if dep not in new_deps:
                            layerbranch.dependencies_set.filter(dependency=dep).delete()
                            reset_last_rev = True

                    if layeritem.vcs_url != last_vcs_url:
                        reset_last_rev = True

                    if reset_last_rev:
                        layerbranch.vcs_last_rev = ''
                        layerbranch.save()
                else:
                    # Save dependencies
                    for dep in form.cleaned_data['deps']:
                        deprec = LayerDependency()
                        deprec.layerbranch = layerbranch
                        deprec.dependency = dep
                        deprec.save()
                    # Send email
                    plaintext = get_template('layerindex/submitemail.txt')
                    perm = Permission.objects.get(codename='publish_layer')
                    users = User.objects.filter(Q(groups__permissions=perm) | Q(user_permissions=perm) ).distinct()
                    for user in users:
                        if user.first_name:
                            user_name = user.first_name
                        else:
                            user_name = user.username
                        layer_url = request.build_absolute_uri(reverse('layer_review', args=(layeritem.name,)))
                        if getattr(settings, 'FORCE_REVIEW_HTTPS', False) and layer_url.startswith('http:'):
                            layer_url = 'https:' + layer_url.split(':', 1)[1]
                        d = {
                            'user_name': user_name,
                            'layer_name': layeritem.name,
                            'layer_url': layer_url,
                        }
                        subject = '%s - %s' % (settings.SUBMIT_EMAIL_SUBJECT, layeritem.name)
                        from_email = settings.SUBMIT_EMAIL_FROM
                        to_email = user.email
                        text_content = plaintext.render(d)
                        tasks.send_email.apply_async((subject, text_content, from_email, [to_email]))
                    return HttpResponseRedirect(reverse('submit_layer_thanks'))

            # Email any new maintainers (that aren't us)
            new_maintainers = layerbranch.layermaintainer_set.exclude(email__in=old_maintainers + [request.user.email])
            if new_maintainers:
                for maintainer in new_maintainers:
                    layer_url = request.build_absolute_uri(reverse('layer_item', args=(layerbranch.branch.name, layeritem.name,)))
                    subjecttext = get_template('layerindex/maintemailsubject.txt')
                    bodytext = get_template('layerindex/maintemail.txt')
                    from_email = settings.SUBMIT_EMAIL_FROM
                    # create subject from subject template
                    d = {
                        'layer_name': layeritem.name,
                        'site_name': request.META['HTTP_HOST'],
                    }
                    subject = subjecttext.render(d).rstrip()

                    #create body from body template
                    d = {
                        'maintainer_name': maintainer.name,
                        'layer_name': layeritem.name,
                        'layer_url': layer_url,
                        'help_contact': _get_help_contact(),
                    }
                    body = bodytext.render(d)

                    tasks.send_email.apply_async((subject, body, from_email, [maintainer.email]))

            messages.success(request, 'Layer %s saved successfully.' % layeritem.name)
            if return_url:
                if returnto == 'layer_review':
                    return_url = reverse_lazy(returnto, args=(layeritem.name,))
                else:
                    return_url = reverse_lazy(returnto, args=(branch, layeritem.name))
                return HttpResponseRedirect(return_url)
    else:
        form = EditLayerForm(request.user, layerbranch, allow_base_type, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(instance=layerbranch)

    return render(request, template_name, {
        'form': form,
        'maintainerformset': maintainerformset,
        'deplistlayers': deplistlayers,
        'allow_base_type': allow_base_type,
        'return_url': return_url,
    })

def bulk_change_edit_view(request, template_name, pk):
    changeset = get_object_or_404(RecipeChangeset, pk=pk)

    if request.method == 'POST':
        formset = BulkChangeEditFormSet(request.POST, queryset=changeset.recipechange_set.all())
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(reverse('bulk_change_review', args=(changeset.id,)))
    else:
        formset = BulkChangeEditFormSet(queryset=changeset.recipechange_set.all())

    return render(request, template_name, {
        'formset': formset,
    })

def bulk_change_patch_view(request, pk):
    changeset = get_object_or_404(RecipeChangeset, pk=pk)
    # FIXME this couples the web server and machine running the update script together,
    # but given that it's a separate script the way is open to decouple them in future
    try:
        ret = utils.runcmd([sys.executable, 'bulkchange.py', str(int(pk)), settings.TEMP_BASE_DIR], os.path.dirname(__file__), shell=False)
        if ret:
            fn = ret.splitlines()[-1]
            if os.path.exists(fn):
                if fn.endswith('.tar.gz'):
                    mimetype = 'application/x-gzip'
                else:
                    mimetype = 'text/x-diff'
                response = HttpResponse(content_type=mimetype)
                response['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(fn)
                with open(fn, "rb") as f:
                    data = f.read()
                    response.write(data)
                os.remove(fn)
                return response
        return HttpResponse('No patch data generated', content_type='text/plain')
    except Exception as e:
        output = getattr(e, 'output', None)
        if output:
            if 'timeout' in output:
                return HttpResponse('Failed to generate patches: timed out waiting for lock. Please try again shortly.', content_type='text/plain')
            else:
                return HttpResponse('Failed to generate patches: %s' % output, content_type='text/plain')
        return HttpResponse('Failed to generate patches: %s' % e, content_type='text/plain')
    # FIXME better error handling


def _check_url_branch(kwargs):
    branchname = kwargs['branch']
    if branchname:
        if branchname == 'oe-classic':
            raise Http404
        branch = get_object_or_404(Branch, name=branchname)

def _get_help_contact():
    # find appropriate help contact
    help_contact = None
    for user in User.objects.all():
        if user.username != 'root' and (user.is_staff or user.is_superuser) and user.is_active:
            help_contact = user
            break
    return help_contact

def publish_view(request, name):
    if not (request.user.is_authenticated and request.user.has_perm('layerindex.publish_layer')):
        raise PermissionDenied

    if getattr(settings, 'SEND_PUBLISH_EMAIL', True):
        layeritem = get_object_or_404(LayerItem, name=name)
        layerbranch = get_object_or_404(LayerBranch, layer=layeritem)
        layer_url = request.build_absolute_uri(reverse('layer_item', args=(layerbranch.branch, layeritem.name)))
        maintainers = get_list_or_404(LayerMaintainer, layerbranch=layerbranch)
        from_email = settings.SUBMIT_EMAIL_FROM
        subjecttext = get_template('layerindex/publishemailsubject.txt')
        bodytext = get_template('layerindex/publishemail.txt')
        maintainer_names = [m.name for m in maintainers]

        # create subject from subject template
        d = {
            'layer_name': layeritem.name,
            'site_name': request.META['HTTP_HOST'],
        }
        subject = subjecttext.render(d).rstrip()

        #create body from body template
        d = {
            'maintainers': maintainer_names,
            'layer_name': layeritem.name,
            'layer_url': layer_url,
            'help_contact': _get_help_contact(),
        }
        body = bodytext.render(d)

        tasks.send_email.apply_async((subject, body, from_email, [m.email for m in maintainers]))

    return _statuschange(request, name, 'P')

def _statuschange(request, name, newstatus):
    w = get_object_or_404(LayerItem, name=name)
    if w.comparison:
        raise Http404
    if w.status != newstatus:
        w.change_status(newstatus, request.user.username)
        w.save()
    return HttpResponseRedirect(w.get_absolute_url())


class RedirectParamsView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        redirect_name = kwargs.pop('redirect_name')
        return reverse_lazy(redirect_name, args=args, kwargs=kwargs)



class LayerListView(ListView):
    context_object_name = 'layerbranch_list'

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        return LayerBranch.objects.filter(branch__name=self.kwargs['branch']).filter(layer__status__in=['P', 'X']).order_by('layer__layer_type', '-layer__index_preference', 'layer__name')

    def get_context_data(self, **kwargs):
        context = super(LayerListView, self).get_context_data(**kwargs)
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        context['layer_type_choices'] = LayerItem.LAYER_TYPE_CHOICES
        return context


class LayerReviewListView(ListView):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('layerindex.publish_layer'):
            raise PermissionDenied
        return super(LayerReviewListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return LayerBranch.objects.filter(branch__name='master').filter(layer__status='N').order_by('layer__name')

class LayerDetailView(DetailView):
    model = LayerItem
    slug_field = 'name'

    # This is a bit of a mess. Surely there has to be a better way to handle this...
    def dispatch(self, request, *args, **kwargs):
        self.user = request.user
        res = super(LayerDetailView, self).dispatch(request, *args, **kwargs)
        l = self.get_object()
        if l:
            if l.comparison:
                raise Http404
            if l.status == 'N':
                if not (request.user.is_authenticated and request.user.has_perm('layerindex.publish_layer')):
                    raise PermissionDenied
        return res

    def get_context_data(self, **kwargs):
        _check_url_branch(self.kwargs)
        context = super(LayerDetailView, self).get_context_data(**kwargs)
        layer = context['layeritem']
        context['useredit'] = layer.user_can_edit(self.user)
        layerbranch = layer.get_layerbranch(self.kwargs['branch'])
        if layerbranch:
            context['layerbranch'] = layerbranch
            context['machines'] = layerbranch.machine_set.order_by('name')
            context['distros'] = layerbranch.distro_set.order_by('name')
            context['appends'] = layerbranch.bbappend_set.order_by('filename')
            context['classes'] = layerbranch.bbclass_set.order_by('name')
            context['updates'] = LayerUpdate.objects.filter(layer=layerbranch.layer, branch=layerbranch.branch).order_by('-started')
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        if 'rrs' in settings.INSTALLED_APPS:
            from rrs.models import MaintenancePlanLayerBranch
            # We don't care about branch, only that the layer is included
            context['rrs_maintplans'] = [m.plan for m in MaintenancePlanLayerBranch.objects.filter(layerbranch__layer=layer)]
        return context

class LayerReviewDetailView(LayerDetailView):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('layerindex.publish_layer'):
            raise PermissionDenied
        return super(LayerReviewDetailView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        self.kwargs['branch'] = 'master'
        context = super(LayerReviewDetailView, self).get_context_data(**kwargs)
        return context


def recipes_preferred_count(qs):
    # Add extra column so we can show "duplicate" recipes from other layers de-emphasised
    # (it's a bit crude having to do this using SQL but I couldn't find a better way...)
    return qs.extra(
        select={
            'preferred_count': """SELECT COUNT(1)
FROM layerindex_recipe AS recipe2
, layerindex_layerbranch as branch2
, layerindex_layeritem as layer1
, layerindex_layeritem as layer2
WHERE branch2.id = recipe2.layerbranch_id
AND layer2.id = branch2.layer_id
AND layer2.layer_type in ('S', 'A')
AND branch2.branch_id = layerindex_layerbranch.branch_id
AND recipe2.pn = layerindex_recipe.pn
AND recipe2.layerbranch_id <> layerindex_recipe.layerbranch_id
AND layer1.id = layerindex_layerbranch.layer_id
AND layer2.index_preference > layer1.index_preference
"""
        },
    )

class RecipeSearchView(ListView):
    context_object_name = 'recipe_list'
    paginate_by = 50

    def render_to_response(self, context, **kwargs):
        if len(self.object_list) == 1:
            return HttpResponseRedirect(reverse('recipe', args=(self.object_list[0].id,)))
        else:
            return super(ListView, self).render_to_response(context, **kwargs)

    def search_recipe_query(self, init_qs, query_string, preferred=True):
        """Do a prioritised search using the specified keyword (if any)"""
        # Lower() here isn't needed for OE recipes since we don't use uppercase
        # but we use this same code for "recipes" from other distros where
        # they do
        order_by = (Lower('pn'), 'layerbranch__layer')

        filtered = False
        if query_string.strip():
            # First search by exact name
            qs0 = init_qs.filter(pn=query_string).order_by(*order_by)
            if preferred:
                qs0 = recipes_preferred_count(qs0)

            # Then keyword somewhere in the name
            entry_query = utils.string_to_query(query_string, ['pn'])
            qs1 = init_qs.filter(entry_query).order_by(*order_by)
            if preferred:
                qs1 = recipes_preferred_count(qs1)

            # Then keyword somewhere in summary or description
            entry_query = utils.string_to_query(query_string, ['description', 'summary'])
            qs2 = init_qs.filter(entry_query).order_by(*order_by)
            if preferred:
                qs2 = recipes_preferred_count(qs2)

            # Now chain the results together and drop any duplicates (e.g.
            # if the keyword matched in the name and summary)
            qs = list(utils.chain_unique(qs0, qs1, qs2))
            filtered = True
        elif 'q' in self.request.GET:
            # User clicked search with no query string, return all records
            qs = init_qs.order_by(*order_by)
            if preferred:
                qs = list(recipes_preferred_count(qs))
        else:
            # It's a bit too slow to return all records by default, and most people
            # won't actually want that (if they do they can just hit the search button
            # with no query string)
            qs = Recipe.objects.none()
        return qs, filtered

    def get_queryset(self):
        import shlex
        _check_url_branch(self.kwargs)
        query_string = self.request.GET.get('q', '')
        init_qs = Recipe.objects.filter(layerbranch__branch__name=self.kwargs['branch'])

        try:
            # Note: we drop quotes here, they will be added back later
            query_items = shlex.split(query_string)
        except ValueError:
            messages.add_message(self.request, messages.ERROR, 'Invalid query string')
            return Recipe.objects.none()
        # Check for single quotes which will cause the filter to blow up (e.g. searching for "'hello'" with all quotes)
        for item in query_items:
            if '\'' in item:
                messages.add_message(self.request, messages.ERROR, 'Invalid query string')
                return Recipe.objects.none()

        inherits = []
        query_terms = []
        for item in query_items:
            # Support slightly crude search on inherits field
            if item.startswith('inherits:'):
                inherits.append(item.split(':')[1])

            # support searches by build dependencies
            elif item.startswith('depends:'):
                depsearch = item.split(':')[1]
                qobj = Q(pk__in=[])
                static_build_dependencies = StaticBuildDep.objects.filter(name=depsearch).first()
                dynamic_build_dependencies = DynamicBuildDep.objects.filter(name=depsearch).first()
                if static_build_dependencies:
                    qobj |= Q(staticbuilddep=static_build_dependencies)
                if dynamic_build_dependencies:
                    qobj |= Q(dynamicbuilddep=dynamic_build_dependencies)
                init_qs = init_qs.filter(qobj).distinct()

            # support searches by layer name
            elif item.startswith('layer:'):
                query_layername = item.split(':')[1].strip().lower()
                if not query_layername:
                    messages.add_message(self.request, messages.ERROR, 'The \
layer name is expected to follow the \"layer:\" prefix without any spaces.')
                else:
                    query_layer = LayerItem.objects.filter(
                        name=query_layername)
                    if query_layername == 'oe-core' and not query_layer:
                        query_layer = LayerItem.objects.filter(name='openembedded-core')
                    if query_layer:
                        init_qs = init_qs.filter(
                            layerbranch__layer=query_layer[0])
                    else:
                        messages.add_message(self.request, messages.ERROR,
                                            'No layer \"%s\" was found.'
                                            % query_layername)
            elif item.startswith('pn:'):
                query_pn = item.split(':')[1].strip().lower()
                init_qs = init_qs.filter(pn=query_pn)
            else:
                if ' ' in item:
                    item = '"%s"' % item
                query_terms.append(item)
        if inherits:
            # FIXME This is a bit ugly, perhaps we should consider having this as a one-many relationship instead
            for inherit in inherits:
                init_qs = init_qs.filter(Q(inherits=inherit) | Q(inherits__startswith=inherit + ' ') | Q(inherits__endswith=' ' + inherit) | Q(inherits__contains=' %s ' % inherit))
        query_string = ' '.join(query_terms)
        qs, _ = self.search_recipe_query(init_qs, query_string, preferred=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super(RecipeSearchView, self).get_context_data(**kwargs)
        searchval = self.request.GET.get('q', '')
        context['search_keyword'] = searchval
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        if searchval:
            context['extra_url_param'] = '?q=%s' % searchval
        return context

class DuplicatesView(TemplateView):
    def get_recipes(self, layer_ids):
        init_qs = Recipe.objects.filter(layerbranch__branch__name=self.kwargs['branch'])
        if layer_ids:
            init_qs = init_qs.filter(layerbranch__layer__in=layer_ids)
        dupes = init_qs.values('pn').annotate(Count('layerbranch', distinct=True)).filter(layerbranch__count__gt=1)
        qs = init_qs.all().filter(pn__in=[item['pn'] for item in dupes]).order_by('pn', 'layerbranch__layer', '-pv')
        return recipes_preferred_count(qs)

    def get_classes(self, layer_ids):
        init_qs = BBClass.objects.filter(layerbranch__branch__name=self.kwargs['branch'])
        if layer_ids:
            init_qs = init_qs.filter(layerbranch__layer__in=layer_ids)
        dupes = init_qs.values('name').annotate(Count('layerbranch', distinct=True)).filter(layerbranch__count__gt=1)
        qs = init_qs.all().filter(name__in=[item['name'] for item in dupes]).order_by('name', 'layerbranch__layer')
        return qs

    def get_incfiles(self, layer_ids):
        init_qs = IncFile.objects.filter(layerbranch__branch__name=self.kwargs['branch'])
        if layer_ids:
            init_qs = init_qs.filter(layerbranch__layer__in=layer_ids)
        dupes = init_qs.values('path').annotate(Count('layerbranch', distinct=True)).filter(layerbranch__count__gt=1)
        qs = init_qs.all().filter(path__in=[item['path'] for item in dupes]).order_by('path', 'layerbranch__layer')
        return qs

    def get_context_data(self, **kwargs):
        layer_ids = [int(i) for i in self.request.GET.getlist('l')]
        context = super(DuplicatesView, self).get_context_data(**kwargs)
        context['recipes'] = self.get_recipes(layer_ids)
        context['classes'] = self.get_classes(layer_ids)
        context['incfiles'] = self.get_incfiles(layer_ids)
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        context['layers'] = LayerBranch.objects.filter(branch__name=self.kwargs['branch']).filter(layer__status__in=['P', 'X']).order_by( 'layer__name')
        context['showlayers'] = layer_ids
        return context

class AdvancedRecipeSearchView(ListView):
    context_object_name = 'recipe_list'
    paginate_by = 50

    def get_queryset(self):
        field = self.request.GET.get('field', '')
        if field:
            search_form = AdvancedRecipeSearchForm(self.request.GET)
            if not search_form.is_valid():
                return Recipe.objects.none()
        match_type = self.request.GET.get('match_type', '')
        if match_type == 'B':
            value = ''
        else:
            value = self.request.GET.get('value', '')
        if value or match_type == 'B':
            if match_type == 'C' or match_type == 'N':
                query = Q(**{"%s__icontains" % field: value})
            else:
                query = Q(**{"%s" % field: value})
            queryset = Recipe.objects.filter(layerbranch__branch__name='master')
            layer = self.request.GET.get('layer', '')
            if layer:
                queryset = queryset.filter(layerbranch__layer=layer)
            if match_type == 'N':
                # Exclude blank as well
                queryset = queryset.exclude(Q(**{"%s" % field: ''})).exclude(query)
            else:
                queryset = queryset.filter(query)
            return queryset.order_by('pn', 'layerbranch__layer')
        return Recipe.objects.none()

    def get_context_data(self, **kwargs):
        context = super(AdvancedRecipeSearchView, self).get_context_data(**kwargs)
        if self.request.GET.get('field', ''):
            searched = True
            search_form = AdvancedRecipeSearchForm(self.request.GET)
        else:
            searched = False
            search_form = AdvancedRecipeSearchForm()
        context['search_form'] = search_form
        context['searched'] = searched
        return context


class BulkChangeView(CreateView):
    model = RecipeChangeset
    form_class = RecipeChangesetForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BulkChangeView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.request.user.is_authenticated:
            raise PermissionDenied
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        return HttpResponseRedirect(reverse('bulk_change_search', args=(obj.id,)))

    def get_context_data(self, **kwargs):
        context = super(BulkChangeView, self).get_context_data(**kwargs)
        context['changesets'] = RecipeChangeset.objects.filter(user=self.request.user)
        return context


class BulkChangeSearchView(AdvancedRecipeSearchView):

    def get(self, request, *args, **kwargs):
        self.changeset = get_object_or_404(RecipeChangeset, pk=kwargs['pk'])
        if self.changeset.user != request.user:
            raise PermissionDenied
        return super(BulkChangeSearchView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied

        changeset = get_object_or_404(RecipeChangeset, pk=kwargs['pk'])
        if changeset.user != request.user:
            raise PermissionDenied

        def add_recipes(recipes):
            for recipe in recipes:
                if not changeset.recipechange_set.filter(recipe=recipe):
                    change = RecipeChange()
                    change.changeset = changeset
                    change.recipe = recipe
                    change.reset_fields()
                    change.save()

        if 'add_selected' in request.POST:
            id_list = request.POST.getlist('selecteditems')
            id_list = [int(i) for i in id_list if i.isdigit()]
            recipes = Recipe.objects.filter(id__in=id_list)
            add_recipes(recipes)
        elif 'add_all' in request.POST:
            add_recipes(self.get_queryset())
        elif 'remove_all' in request.POST:
            changeset.recipechange_set.all().delete()

        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BulkChangeSearchView, self).get_context_data(**kwargs)
        context['changeset'] = self.changeset
        context['current_branch'] = 'master'
        return context


class BaseDeleteView(DeleteView):

    def get_context_data(self, **kwargs):
        context = super(BaseDeleteView, self).get_context_data(**kwargs)
        obj = context.get('object', None)
        if obj:
            context['object_type'] = obj._meta.verbose_name
            cancel = self.request.GET.get('cancel', '')
            if cancel:
                context['cancel_url'] = reverse_lazy(cancel, args=(obj.pk,))
        return context


class BulkChangeDeleteView(BaseDeleteView):
    model = RecipeChangeset
    success_url = reverse_lazy('bulk_change')

    def get_queryset(self):
        qs = super(BulkChangeDeleteView, self).get_queryset()
        return qs.filter(user=self.request.user)


class MachineSearchView(ListView):
    context_object_name = 'machine_list'
    paginate_by = 50

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        if self.request.GET.get('search', ''):
            query_string = self.request.GET.get('q', '')
        else:
            query_string = ""
        init_qs = Machine.objects.filter(layerbranch__branch__name=self.kwargs['branch'])
        if query_string.strip():
            entry_query = utils.string_to_query(query_string, ['name', 'description'])
            return init_qs.filter(entry_query).order_by('name', 'layerbranch__layer')
        else:
            if 'q' in self.request.GET:
                return init_qs.order_by('name', 'layerbranch__layer')
            else:
                # Be consistent with RecipeSearchView
                return Machine.objects.none()

    def get_context_data(self, **kwargs):
        context = super(MachineSearchView, self).get_context_data(**kwargs)
        context['search_keyword'] = self.request.GET.get('q', '')
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        return context


class UpdateListView(ListView):
    context_object_name = "updates"
    paginate_by = 50

    def get_queryset(self):
        return Update.objects.all().order_by('-started')


class UpdateDetailView(DetailView):
    model = Update

    def get_context_data(self, **kwargs):
        context = super(UpdateDetailView, self).get_context_data(**kwargs)
        update = self.get_object()
        if update:
            context['layerupdates'] = update.layerupdate_set.order_by('-started')
        return context


class LayerUpdateDetailView(DetailView):
    model = LayerUpdate


class DistroSearchView(ListView):
    context_object_name = 'distro_list'
    paginate_by = 50

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        if self.request.GET.get('search', ''):
            query_string = self.request.GET.get('q', '')
        else:
            query_string = ""
        init_qs = Distro.objects.filter(layerbranch__branch__name=self.kwargs['branch'])
        if query_string.strip():
            entry_query = utils.string_to_query(query_string, ['name', 'description'])
            return init_qs.filter(entry_query).order_by('name', 'layerbranch__layer')

        if 'q' in self.request.GET:
            return init_qs.order_by('name', 'layerbranch__layer')

        # Be consistent with RecipeSearchView
        return Distro.objects.none()

    def get_context_data(self, **kwargs):
        context = super(DistroSearchView, self).get_context_data(**kwargs)
        context['search_keyword'] = self.request.GET.get('q', '')
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        return context

class ClassSearchView(ListView):
    context_object_name = 'class_list'
    paginate_by = 50

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        if self.request.GET.get('search', ''):
            query_string = self.request.GET.get('q', '')
        else:
            query_string = ""
        init_qs = BBClass.objects.filter(layerbranch__branch__name=self.kwargs['branch'])
        if query_string.strip():
            entry_query = utils.string_to_query(query_string, ['name'])
            return init_qs.filter(entry_query).order_by('name', 'layerbranch__layer')

        if 'q' in self.request.GET:
            return init_qs.order_by('name', 'layerbranch__layer')

        # Be consistent with RecipeSearchView
        return BBClass.objects.none()

    def get_context_data(self, **kwargs):
        context = super(ClassSearchView, self).get_context_data(**kwargs)
        context['search_keyword'] = self.request.GET.get('q', '')
        context['url_branch'] = self.kwargs['branch']
        context['this_url_name'] = resolve(self.request.path_info).url_name
        return context

class HistoryListView(ListView):
    context_object_name = "revisions"
    paginate_by = 50

    def get_queryset(self):
        return Revision.objects.all().order_by('-date_created')


class EditProfileFormView(SuccessMessageMixin, UpdateView):
    form_class = EditProfileForm

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        self.user = request.user
        return super(EditProfileFormView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(EditProfileFormView, self).get_context_data(**kwargs)
        form = context['form']
        # Prepare a list of fields with errors
        # We do this so that if there's a problem with the captcha, that's the only error shown
        # (since we have a username field, we want to make user enumeration difficult)
        if 'captcha' in form.errors:
            error_fields = ['captcha']
        else:
            error_fields = form.errors.keys()
        context['error_fields'] = error_fields
        context['return_url'] = self.get_success_url()
        return context

    def get_object(self, queryset=None):
        return self.user

    def form_valid(self, form):
        self.object = form.save()

        if'answer_1' in form.changed_data:
            # If one security answer has changed, they all have. Delete current questions and add new ones.
            # Don't throw an error if we are editing the super user and they don't have security questions yet.
            try:
                self.user.userprofile.securityquestionanswer_set.all().delete()
                user = self.user.userprofile
            except UserProfile.DoesNotExist:
                user = UserProfile.objects.create(user=self.user)

            security_question_1 = SecurityQuestion.objects.get(question=form.cleaned_data.get("security_question_1"))
            security_question_2 = SecurityQuestion.objects.get(question=form.cleaned_data.get("security_question_2"))
            security_question_3 = SecurityQuestion.objects.get(question=form.cleaned_data.get("security_question_3"))
            answer_1 = form.cleaned_data.get("answer_1").replace(" ", "").lower()
            answer_2 = form.cleaned_data.get("answer_2").replace(" ", "").lower()
            answer_3 = form.cleaned_data.get("answer_3").replace(" ", "").lower()

            # Answers are hashed using Django's password hashing function make_password()
            SecurityQuestionAnswer.objects.create(user=user, security_question=security_question_1,
                                                  answer=make_password(answer_1))
            SecurityQuestionAnswer.objects.create(user=user, security_question=security_question_2,
                                                  answer=make_password(answer_2))
            SecurityQuestionAnswer.objects.create(user=user, security_question=security_question_3,
                                                  answer=make_password(answer_3))

        if 'email' in form.changed_data:
            # Take a copy of request.user as it is about to be invalidated by logout()
            user = self.request.user
            logout(self.request)
            # Deactivate user and put through registration again
            user.is_active = False
            user.save()
            view = RegistrationView()
            view.request = self.request
            view.send_activation_email(user)
            return HttpResponseRedirect(reverse('reregister'))

        return super(EditProfileFormView, self).form_valid(form)

    def get_success_message(self, cleaned_data):
        return "Profile saved successfully"

    def get_success_url(self):
        return self.request.GET.get('return_to', reverse('frontpage'))


@receiver(pre_save, sender=reversion.models.Version)
def annotate_revision_version(sender, instance, *args, **kwargs):
    ignorefields = ['vcs_last_rev', 'vcs_last_fetch', 'vcs_last_commit', 'updated']
    changelist = []
    objclass = instance.content_type.model_class()
    currentVersion = instance.field_dict
    #FIXME modern django-reversion dropped the type field (argh!)
    #if instance.type == reversion.models.VERSION_DELETE:
    #    changelist.append("Deleted %s: %s" % (modelmeta.verbose_name.lower(), instance.object_repr))
    #else:
    pastver = reversion.models.Version.objects.filter(content_type=instance.content_type, object_id=instance.object_id).order_by('-id').first()
    if pastver:# and instance.type != reversion.models.VERSION_ADD:
        pastVersion = pastver.field_dict
        changes = set(currentVersion.items()) - set(pastVersion.items())
        changedVars = [var[0] for var in changes]
        fieldchanges = []
        modelmeta = objclass._meta
        for field in changedVars:
            if field not in ignorefields:
                modelfield = modelmeta.get_field(field)
                newvalue = currentVersion[field]
                if modelfield.choices:
                    for v in modelfield.choices:
                        if v[0] == newvalue:
                            newvalue = v[1]
                            break
                fieldchanges.append("%s to '%s'" % (modelfield.verbose_name.lower(), newvalue))
        if fieldchanges:
            changelist.append("Changed %s %s %s" % (modelmeta.verbose_name.lower(), instance.object_repr, ", ".join(fieldchanges)))
    if changelist:
        if not instance.revision.comment or instance.revision.comment == 'No changes':
            instance.revision.comment = '\n'.join(changelist)
        else:
            instance.revision.comment = instance.revision.comment + '\n' + ('\n'.join(changelist))
        instance.revision.save()


@receiver(pre_save, sender=reversion.models.Revision)
def annotate_revision(sender, instance, *args, **kwargs):
    if instance.pk is None:
        # When you make changes in the admin site the comment gets set to just
        # specify the field that was changed, but that's not enough detail.
        # For changes elsewhere it'll be blank since we aren't creating a revision
        # explicitly. Thus, set the comment to a default value and we'll fill it in
        # ourselves using the Version pre-save signal handler above.
        instance.comment = 'No changes'


class RecipeDetailView(DetailView):
    model = Recipe

    def get_context_data(self, **kwargs):
        context = super(RecipeDetailView, self).get_context_data(**kwargs)
        recipe = self.get_object()
        if recipe:
            verappendprefix = recipe.filename.split('.bb')[0]
            appendprefix = verappendprefix.split('_')[0]
            appendprefix = appendprefix.replace('+', r'\+')
            #context['verappends'] = BBAppend.objects.filter(layerbranch__branch=recipe.layerbranch.branch).filter(filename='%s.bbappend' % verappendprefix)
            context['appends'] = BBAppend.objects.filter(layerbranch__branch=recipe.layerbranch.branch).filter(filename__regex=r'^%s(_[^_]*)?\.bbappend' % appendprefix)
            verappends = []
            for append in context['appends']:
                if append.matches_recipe(recipe):
                    verappends.append(append)
            context['verappends'] = verappends
            context['packageconfigs'] = recipe.packageconfig_set.order_by('feature')
            context['staticdependencies'] = recipe.staticbuilddep_set.order_by('name')
            extrafiles = []
            for dep in recipe.recipefiledependency_set.all():
                if dep.path.endswith('.inc'):
                    extrafiles.append(dep)
            context['extrafiles'] = extrafiles
            context['otherbranch_recipes'] = Recipe.objects.filter(layerbranch__layer=recipe.layerbranch.layer, layerbranch__branch__comparison=False, pn=recipe.pn).order_by('layerbranch__branch__sort_priority')
        return context


class LinkWrapper:
    def __init__(self, queryset):
        self.queryset = queryset

    def __iter__(self):
        for obj in self.queryset:
            self._annotate(obj)
            yield obj

    def _slice(self, start, stop, step=1):
        for item in islice(self.queryset, start, stop, step):
            self._annotate(item)
            yield item

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self._slice(key.start, key.stop, key.step)
        else:
            return next(self._slice(key, key+1))

    def __len__(self):
        if isinstance(self.queryset, QuerySet):
            return self.queryset.count()
        else:
            return len(self.queryset)

class ClassicRecipeLinkWrapper(LinkWrapper):
    # This function is required by generic views, create another proxy
    def _clone(self):
        return ClassicRecipeLinkWrapper(self.queryset._clone(), **self.kwargs)

    def _annotate(self, obj):
        recipe = None
        vercmp = 0
        if obj.cover_layerbranch and obj.cover_pn:
            rq = Recipe.objects.filter(layerbranch=obj.cover_layerbranch).filter(pn=obj.cover_pn)
            if rq:
                recipe = rq.first()
                if obj.pv and recipe.pv:
                    obj_ver = parse_version(obj.pv)
                    recipe_ver = parse_version(recipe.pv)
                    vercmp = ((recipe_ver > obj_ver) - (recipe_ver < obj_ver))
        setattr(obj, 'cover_recipe', recipe)
        setattr(obj, 'cover_vercmp', vercmp)

class ClassicRecipeReverseLinkWrapper(LinkWrapper):
    def __init__(self, queryset, branch):
        self.queryset = queryset
        self.branch = branch

    # This function is required by generic views, create another proxy
    def _clone(self):
        return ClassicRecipeReverseLinkWrapper(self.queryset._clone(), **self.kwargs)

    def _annotate(self, obj):
        recipe = None
        vercmp = 0
        rq = ClassicRecipe.objects.filter(layerbranch__branch__name=self.branch).filter(cover_layerbranch=obj.layerbranch).filter(cover_pn=obj.pn)
        if rq:
            recipe = rq.first()
            if obj.pv and recipe.pv:
                obj_ver = parse_version(obj.pv)
                recipe_ver = parse_version(recipe.pv)
                vercmp = ((recipe_ver > obj_ver) - (recipe_ver < obj_ver))
        setattr(obj, 'cover_recipe', recipe)
        setattr(obj, 'cover_vercmp', vercmp)


class LayerCheckListView(ListView):
    context_object_name = 'layerbranches'

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        return LayerBranch.objects.filter(branch__name=self.kwargs['branch']).filter(layer__status__in=['P', 'X']).order_by('layer__name')

class BBClassCheckListView(ListView):
    context_object_name = 'classes'

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        nonrecipe_classes = ['archiver',
                             'base',
                             'buildhistory',
                             'bugzilla',
                             'buildstats',
                             'buildstats-summary',
                             'ccache',
                             'chrpath',
                             'copyleft_compliance',
                             'copyleft_filter',
                             'cve-check',
                             'debian',
                             'devshell',
                             'devtool-source',
                             'distrodata',
                             'extrausers',
                             'icecc',
                             'image-buildinfo',
                             'image-container',
                             'image-combined-dbg',
                             'image-live',
                             'image-mklibs',
                             'image-prelink',
                             'image_types',
                             'image_types_wic',
                             'insane',
                             'license',
                             'license_image',
                             'live-vm-common',
                             'logging',
                             'metadata_scm',
                             'migrate_localcount',
                             'mirrors',
                             'multilib',
                             'multilib_global',
                             'multilib_header',
                             'oelint',
                             'own-mirrors',
                             'package',
                             'package_deb',
                             'package_ipk',
                             'package_rpm',
                             'package_tar',
                             'packagedata',
                             'packagefeed-stability',
                             'patch',
                             'primport',
                             'prexport',
                             'recipe_sanity',
                             'remove-libtool',
                             'report-error',
                             'reproducible_build',
                             'reproducible_build_simple',
                             'rm_work',
                             'rm_work_and_downloads',
                             'rootfs-postcommands',
                             'rootfs_deb',
                             'rootfs_ipk',
                             'rootfs_rpm',
                             'rootfsdebugfiles',
                             'sanity',
                             'sign_ipk',
                             'sign_package_feed',
                             'sign_rpm',
                             'siteconfig',
                             'siteinfo',
                             'spdx',
                             'sstate',
                             'staging',
                             'syslinux',
                             'systemd-boot',
                             'terminal',
                             'testexport',
                             'testimage',
                             'testimage-auto',
                             'testsdk',
                             'tinderclient',
                             'toaster',
                             'toolchain-scripts',
                             'toolchain-scripts-base',
                             'uninative',
                             'useradd-staticids',
                             'utility-tasks',
                             'utils',
                             ]
        return BBClass.objects.filter(layerbranch__branch__name=self.kwargs['branch']).filter(layerbranch__layer__name=settings.CORE_LAYER_NAME).exclude(name__in=nonrecipe_classes).order_by('name')


class ClassicRecipeSearchView(RecipeSearchView):
    def render_to_response(self, context, **kwargs):
        # Bypass the redirect-to-single-instance behaviour of RecipeSearchView
        return super(ListView, self).render_to_response(context, **kwargs)

    def get_queryset(self):
        self.kwargs['branch'] = self.kwargs.get('branch', 'oe-classic')
        query_string = self.request.GET.get('q', '')
        cover_status = self.request.GET.get('cover_status', None)
        cover_verified = self.request.GET.get('cover_verified', None)
        category = self.request.GET.get('category', None)
        selectedlayers_param = self.request.GET.get('selectedlayers', '')
        if selectedlayers_param:
            layer_ids = [int(i) for i in selectedlayers_param.split(',')]
        else:
            layer_ids = []
        has_patches = self.request.GET.get('has_patches', '')
        needs_attention = self.request.GET.get('needs_attention', '')
        qreversed = self.request.GET.get('reversed', '')
        init_qs = ClassicRecipe.objects.filter(layerbranch__branch__name=self.kwargs['branch']).filter(deleted=False)
        filtered = False
        cover_null = False
        if cover_status:
            if cover_status == '!':
                init_qs = init_qs.filter(cover_status__in=['U', 'N'])
            elif cover_status == '#':
                init_qs = init_qs.exclude(cover_status__in=['U', 'N', 'S'])
            else:
                init_qs = init_qs.filter(cover_status=cover_status)
            filtered = True
            if cover_status in ['U', '!']:
                cover_null = True
        if cover_verified:
            init_qs = init_qs.filter(cover_verified=(cover_verified=='1'))
            filtered = True
        if category:
            if category == "''" or category == '""':
                init_qs = init_qs.filter(classic_category='')
            else:
                init_qs = init_qs.filter(classic_category__icontains=category)
            filtered = True
        if layer_ids:
            init_qs = init_qs.filter(cover_layerbranch__layer__in=layer_ids)
        if has_patches.strip():
            if has_patches == '1':
                init_qs = init_qs.filter(patch__isnull=False).distinct()
            else:
                init_qs = init_qs.filter(patch__isnull=True)
            filtered = True
        if needs_attention.strip():
            if needs_attention == '1':
                init_qs = init_qs.filter(needs_attention=True)
            else:
                init_qs = init_qs.filter(needs_attention=False)
            filtered = True
        qs, filtered = self.search_recipe_query(init_qs, query_string, preferred=False)
        if qreversed:
            init_rqs = Recipe.objects.filter(layerbranch__branch__name='master')
            if layer_ids:
                init_rqs = init_rqs.filter(layerbranch__layer__id__in=layer_ids)
            excludeclasses_param = self.request.GET.get('excludeclasses', '')
            if excludeclasses_param:
                for inherit in excludeclasses_param.split(','):
                    init_rqs = init_rqs.exclude(inherits=inherit).exclude(inherits__startswith=inherit + ' ').exclude(inherits__endswith=' ' + inherit).exclude(inherits__contains=' %s ' % inherit)
            all_values = []
            if filtered:
                if isinstance(qs, list):
                    values = []
                    for item in qs:
                        if item.cover_layerbranch and item.cover_pn:
                            values.append((item.cover_layerbranch.id, item.cover_pn))
                else:
                    values = qs.filter(cover_layerbranch__isnull=False).filter(cover_pn__isnull=False).values_list('cover_layerbranch__id', 'cover_pn').distinct()
                if cover_null:
                    all_values = ClassicRecipe.objects.filter(layerbranch__branch__name=self.kwargs['branch']).filter(deleted=False).filter(cover_layerbranch__isnull=False).filter(cover_pn__isnull=False).values_list('cover_layerbranch__id', 'cover_pn').distinct()
            else:
                values = None
            rqs = init_rqs.order_by(Lower('pn'), 'layerbranch__layer')
            if filtered:
                items = []
                for item in rqs:
                    recipe_values = (item.layerbranch.id, item.pn)
                    if (cover_null and recipe_values not in all_values) or (recipe_values in values):
                        items.append(item)
                return ClassicRecipeReverseLinkWrapper(items, self.kwargs['branch'])
            return ClassicRecipeReverseLinkWrapper(rqs, self.kwargs['branch'])
        else:
            return ClassicRecipeLinkWrapper(qs)

    def get_context_data(self, **kwargs):
        context = super(ClassicRecipeSearchView, self).get_context_data(**kwargs)
        context['this_url_name'] = 'recipe_search'
        branchname = self.kwargs.get('branch', 'oe-classic')
        context['branch'] = get_object_or_404(Branch, name=branchname)
        if 'q' in self.request.GET:
            searched = True
            search_form = ClassicRecipeSearchForm(self.request.GET)
        else:
            searched = False
            search_form = ClassicRecipeSearchForm()
        context['compare'] = self.request.GET.get('compare', False)
        context['reversed'] = self.request.GET.get('reversed', False)
        context['search_form'] = search_form
        context['searched'] = searched
        selectedlayers_param = self.request.GET.get('selectedlayers', '')
        if selectedlayers_param:
            all_layer_names = dict(LayerItem.objects.all().values_list('id', 'name'))
            layer_ids = [int(i) for i in selectedlayers_param.split(',')]
            layer_names = [all_layer_names[i] for i in layer_ids]
            context['selectedlayers_display'] = ','.join(layer_names)
        else:
            layer_ids = []
            context['selectedlayers_display'] = ' (any)'
        context['selectedlayers'] = layer_ids

        excludeclasses_param = self.request.GET.get('excludeclasses', '')
        if excludeclasses_param:
            context['excludeclasses_display'] = excludeclasses_param
            context['excludeclasses'] = excludeclasses_param.split(',')
        else:
            context['excludeclasses_display'] = ' (none)'
            context['excludeclasses'] = []

        context['updateable'] = False
        if self.request.user.has_perm('layerindex.update_comparison_branch'):
            for item in getattr(settings, 'COMPARISON_UPDATE', []):
                if item['branch_name'] == context['branch'].name:
                    context['updateable'] = True
                    break

        return context



class ClassicRecipeDetailView(SuccessMessageMixin, DetailView):
    model = ClassicRecipe
    context_object_name = 'recipe'

    def _can_edit(self):
        if self.request.user.is_authenticated:
            if not self.request.user.has_perm('layerindex.edit_classic'):
                return False
        else:
            return False
        return True

    def _can_disposition_patches(self):
        if self.request.user.is_authenticated:
            if not self.request.user.has_perm('layerindex.patch_disposition'):
                return False
        else:
            return False
        return True

    def get_context_data(self, **kwargs):
        context = super(ClassicRecipeDetailView, self).get_context_data(**kwargs)
        context['can_edit'] = self._can_edit()
        recipe = context['recipe']
        context['branch'] = recipe.layerbranch.branch
        # Get covering recipe if any
        cover_recipe = None
        if recipe.cover_pn:
            rq = Recipe.objects.filter(layerbranch=recipe.cover_layerbranch).filter(pn=recipe.cover_pn)
            if rq:
                cover_recipe = rq.first()
        context['cover_recipe'] = cover_recipe
        context['layerbranch_desc'] = str(recipe.layerbranch.branch)
        context['to_desc'] = 'OpenEmbedded'
        context['recipes'] = [recipe, cover_recipe]

        context['can_disposition_patches'] = self._can_disposition_patches()
        if context['can_disposition_patches']:
            nodisposition_ids = list(recipe.patch_set.filter(patchdisposition__isnull=True).values_list('id', flat=True))
            patch_initial = [{'patch': p} for p in nodisposition_ids]
            patch_formset = PatchDispositionFormSet(queryset=PatchDisposition.objects.filter(patch__recipe=recipe), initial=patch_initial, prefix='patchdispositiondialog')
            patch_formset.extra = len(patch_initial)
            context['patch_formset'] = patch_formset
        return context

    def post(self, request, *args, **kwargs):
        if not self._can_disposition_patches():
            raise PermissionDenied

        recipe = get_object_or_404(ClassicRecipe, pk=self.kwargs['pk'])
        # What follows is a bit hacky, because we are receiving the form fields
        # for just one of the forms in the formset which isn't really supported
        # by Django
        for field in request.POST:
            if field.startswith('patchdispositiondialog'):
                prefix = '-'.join(field.split('-')[:2])
                instance = None
                patchdisposition_id = request.POST.get('%s-id' % prefix, '')
                if patchdisposition_id != '':
                    instance = get_object_or_404(PatchDisposition, pk=int(patchdisposition_id))

                form = PatchDispositionForm(request.POST, prefix=prefix, instance=instance)
                if form.is_valid():
                    instance = form.save(commit=False)
                    instance.user = request.user
                    instance.save()
                    messages.success(request, 'Changes to patch %s saved successfully.' % instance.patch.src_path)
                    return HttpResponseRedirect(reverse('comparison_recipe', args=(recipe.id,)))
                else:
                    # FIXME this is ugly because HTML gets escaped
                    messages.error(request, 'Failed to save changes: %s' % form.errors)
                break

        return self.get(request, *args, **kwargs)


class ClassicRecipeStatsView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super(ClassicRecipeStatsView, self).get_context_data(**kwargs)
        branchname = self.kwargs.get('branch', 'oe-classic')
        context['branch'] = get_object_or_404(Branch, name=branchname)
        context['url_branch'] = branchname
        context['this_url_name'] = 'recipe_search'
        # *** Cover status chart ***
        recipes = ClassicRecipe.objects.filter(layerbranch__branch=context['branch']).filter(deleted=False)
        statuses = []
        status_counts = {}
        for choice, desc in ClassicRecipe.COVER_STATUS_CHOICES:
            count = recipes.filter(cover_status=choice).count()
            if count > 0:
                statuses.append(desc)
                status_counts[desc] = count
        statuses = sorted(statuses, key=lambda status: status_counts[status], reverse=True)
        context['chart_status_labels'] = statuses
        context['chart_status_values'] = [status_counts[status] for status in statuses]
        # *** Categories chart ***
        categories = ['obsoletedir', 'nonworkingdir']
        uniquevals = recipes.exclude(classic_category='').values_list('classic_category', flat=True).distinct()
        for value in uniquevals:
            cats = value.split()
            for cat in cats:
                if not cat in categories:
                    categories.append(cat)
        categories.append('none')
        catcounts = dict.fromkeys(categories, 0)
        unmigrated = recipes.filter(cover_status__in=['U', 'N'])
        catcounts['none'] = unmigrated.filter(classic_category='').count()
        values = unmigrated.exclude(classic_category='').values_list('classic_category', flat=True)
        # We gather data this way because an item might be in more than one category, thus
        # the categories list must be in priority order
        for value in values:
            recipecats = value.split()
            foundcat = 'none'
            for cat in categories:
                if cat in recipecats:
                    foundcat = cat
                    break
            catcounts[foundcat] += 1
        # Eliminate categories with zero count
        categories = [cat for cat in categories if catcounts[cat] > 0]
        categories = sorted(categories, key=lambda cat: catcounts[cat], reverse=True)
        context['chart_category_labels'] = categories
        context['chart_category_values'] = [catcounts[k] for k in categories]
        return context


class StatsView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super(StatsView, self).get_context_data(**kwargs)
        context['layercount'] = LayerItem.objects.count()
        context['recipe_count_distinct'] = Recipe.objects.values('pn').distinct().count()
        context['class_count_distinct'] = BBClass.objects.values('name').distinct().count()
        context['machine_count_distinct'] = Machine.objects.values('name').distinct().count()
        context['distro_count_distinct'] = Distro.objects.values('name').distinct().count()
        context['perbranch'] = Branch.objects.filter(hidden=False).order_by('sort_priority').annotate(
                layer_count=Count('layerbranch', distinct=True),
                recipe_count=Count('layerbranch__recipe', distinct=True),
                class_count=Count('layerbranch__bbclass', distinct=True),
                machine_count=Count('layerbranch__machine', distinct=True),
                distro_count=Count('layerbranch__distro', distinct=True))
        return context


def layer_export_recipes_csv_view(request, branch, slug):
    import csv
    layer = get_object_or_404(LayerItem, name=slug)
    layerbranch = layer.get_layerbranch(branch)
    if not layerbranch:
        raise Http404

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="recipes_%s_%s.csv"' % (layer.name, layerbranch.branch.name)

    fieldlist = request.GET.get('fields', 'pn,pv,license').split(',')
    recipe_fields = [f.name for f in Recipe._meta.get_fields() if not (f.auto_created and f.is_relation)]
    for field in fieldlist:
        if field not in recipe_fields:
            return HttpResponse('Field %s is invalid' % field)

    writer = csv.writer(response)
    for recipe in layerbranch.sorted_recipes():
        values = [getattr(recipe, field) for field in fieldlist]
        writer.writerow(values)

    return response


def comparison_update_view(request, branch):
    branchobj = get_object_or_404(Branch, name=branch)
    if not branchobj.comparison:
        raise Http404
    if not request.user.has_perm('layerindex.update_comparison_branch'):
        raise PermissionDenied

    from celery import uuid

    cmd = None
    for item in getattr(settings, 'COMPARISON_UPDATE', []):
        if item['branch_name'] == branchobj.name:
            cmd = item['update_command']
            break
    if not cmd:
        raise Exception('No update command defined for branch %s' % branch)

    task_id = uuid()
    # Create this here first, because inside the task we don't have all of the required info
    update = Update(task_id=task_id)
    update.started = datetime.now()
    update.triggered_by = request.user
    update.save()

    res = tasks.run_update_command.apply_async((branch, cmd), task_id=task_id)

    return HttpResponseRedirect(reverse_lazy('task_status', kwargs={'task_id': task_id}))


class TaskStatusView(TemplateView):
    def get_context_data(self, **kwargs):
        from celery.result import AsyncResult
        context = super(TaskStatusView, self).get_context_data(**kwargs)
        task_id = self.kwargs['task_id']
        context['task_id'] = task_id
        context['result'] = AsyncResult(task_id)
        context['update'] = get_object_or_404(Update, task_id=task_id)
        context['log_url'] = reverse_lazy('task_log', args=(task_id,))
        return context

def task_log_view(request, task_id):
    from celery.result import AsyncResult
    if not request.user.is_authenticated:
        raise PermissionDenied

    if '/' in task_id:
        # Block anything that looks like a path
        raise Http404

    result = AsyncResult(task_id)
    start = int(request.GET.get('start', 0))
    try:
        f = open(os.path.join(settings.TASK_LOG_DIR, 'task_%s.log' % task_id), 'rb')
    except FileNotFoundError:
        raise Http404
    try:
        f.seek(start)
        datastr = f.read()
        origlen = len(datastr)
        # Squash out CRs *within* the string (CRs at the start preserved)
        datastr = re.sub(b'\n[^\n]+\r', b'\n', datastr)
        # We need to escape this or else things that look like tags in the output
        # will be interpreted as such by the browser
        data = escape(datastr)
        response = HttpResponse(data)
        try:
            ready = result.ready()
        except ConnectionResetError:
            # FIXME this shouldn't be happening so often, but ultimately we don't care -
            # the frontend is polling so it'll likely succeed in a subsequent request
            ready = False
        if ready:
            response['Task-Done'] = '1'
            updateobj = get_object_or_404(Update, task_id=task_id)
            response['Task-Duration'] = utils.timesince2(updateobj.started, updateobj.finished)
            response['Task-Progress'] = 100
            if result.info:
                if isinstance(result.info, dict):
                    response['Task-Result'] = result.info.get('retcode', None)
                else:
                    response['Task-Result'] = -1
        else:
            response['Task-Done'] = '0'
            preader = utils.ProgressReader(settings.TASK_LOG_DIR, task_id)
            response['Task-Progress'] = preader.read()
        response['Task-Log-Position'] = start + origlen
    finally:
        f.close()
    return response

def task_stop_view(request, task_id):
    from celery.result import AsyncResult
    import signal
    if not request.user.is_authenticated:
        raise PermissionDenied

    result = AsyncResult(task_id)
    result.revoke(terminate=True, signal=signal.SIGUSR2)
    return HttpResponse('terminated')


def email_test_view(request):
    if not request.user.is_authenticated and request.user.is_staff():
        raise PermissionDenied

    plaintext = get_template('layerindex/testemail.txt')
    if request.user.first_name:
        user_name = request.user.first_name
    else:
        user_name = request.user.username
    site = Site.objects.get_current()
    if site:
        site_name = site.name
    else:
        site_name = 'OE Layer Index'
    d = {
        'user_name': user_name,
        'site_name': site_name,
        'site_host': request.META['HTTP_HOST'],
        'help_contact': _get_help_contact(),
    }
    subject = '%s: test email' % site_name
    from_email = settings.SUBMIT_EMAIL_FROM
    to_email = request.user.email
    text_content = plaintext.render(d)
    tasks.send_email.apply_async((subject, text_content, from_email, [to_email]))
    return HttpResponse('Test email sent to %s' % to_email)


class ComparisonRecipeSelectView(ClassicRecipeSearchView):
    def _can_edit(self):
        if self.request.user.is_authenticated:
            if not self.request.user.has_perm('layerindex.edit_classic'):
                return False
        else:
            return False
        return True

    def get_context_data(self, **kwargs):
        self.kwargs['branch'] = 'master'
        context = super(ComparisonRecipeSelectView, self).get_context_data(**kwargs)
        recipe = get_object_or_404(ClassicRecipe, pk=self.kwargs['pk'])
        context['select_for'] = recipe
        context['existing_cover_recipe'] = recipe.get_cover_recipe()
        comparison_form = ClassicRecipeForm(prefix='selectrecipedialog', instance=recipe)
        comparison_form.fields['cover_pn'].widget = forms.HiddenInput()
        comparison_form.fields['cover_layerbranch'].widget = forms.HiddenInput()
        context['comparison_form'] = comparison_form

        if 'q' in self.request.GET:
            search_form = ComparisonRecipeSelectForm(self.request.GET)
        else:
            search_form = ComparisonRecipeSelectForm()
        context['search_form'] = search_form

        context['can_edit'] = self._can_edit()
        return context

    def get_queryset(self):
        query_string = self.request.GET.get('q', '')
        selectedlayers_param = self.request.GET.get('selectedlayers', '')
        if selectedlayers_param:
            layer_ids = [int(i) for i in selectedlayers_param.split(',')]
        else:
            layer_ids = []
        init_qs = Recipe.objects.filter(layerbranch__branch__name='master')
        if layer_ids:
            init_qs = init_qs.filter(layerbranch__layer__in=layer_ids)
        qs, _ = self.search_recipe_query(init_qs, query_string, preferred=False)
        return qs

    def post(self, request, *args, **kwargs):
        if not self._can_edit():
            raise PermissionDenied

        recipe = get_object_or_404(ClassicRecipe, pk=self.kwargs['pk'])
        form = ClassicRecipeForm(request.POST, prefix='selectrecipedialog', instance=recipe)

        if form.is_valid():
            form.save()
            messages.success(request, 'Changes to comparison recipe %s saved successfully.' % recipe.pn)
            return HttpResponseRedirect(reverse('comparison_recipe', args=(recipe.id,)))
        else:
            # FIXME this is ugly because HTML gets escaped
            messages.error(request, 'Failed to save changes: %s' % form.errors)

        return self.get(request, *args, **kwargs)


class ComparisonRecipeSelectDetailView(DetailView):
    model = Recipe

    def get_context_data(self, **kwargs):
        context = super(ComparisonRecipeSelectDetailView, self).get_context_data(**kwargs)
        recipe = get_object_or_404(ClassicRecipe, pk=self.kwargs['selectfor'])
        context['select_for'] = recipe
        context['existing_cover_recipe'] = recipe.get_cover_recipe()
        comparison_form = ClassicRecipeForm(prefix='selectrecipedialog', instance=recipe)
        comparison_form.fields['cover_pn'].widget = forms.HiddenInput()
        comparison_form.fields['cover_layerbranch'].widget = forms.HiddenInput()
        context['comparison_form'] = comparison_form
        context['can_edit'] = False
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied

        recipe = get_object_or_404(ClassicRecipe, pk=self.kwargs['selectfor'])
        form = ClassicRecipeForm(request.POST, prefix='selectrecipedialog', instance=recipe)

        if form.is_valid():
            form.save()
            messages.success(request, 'Changes to comparison recipe %s saved successfully.' % recipe.pn)
            return HttpResponseRedirect(reverse('comparison_recipe', args=(recipe.id,)))
        else:
            # FIXME this is ugly because HTML gets escaped
            messages.error(request, 'Failed to save changes: %s' % form.errors)

        return self.get(request, *args, **kwargs)


class BranchCompareView(FormView):
    form_class = BranchComparisonForm

    def get_recipes(self, from_branch, to_branch, layer_ids):
        from distutils.version import LooseVersion
        class BranchComparisonResult:
            def __init__(self, pn, short_desc):
                self.pn = pn
                self.short_desc = short_desc
                self.from_versions = []
                self.to_versions = []
                self.id = None
            def pv_changed(self):
                from_pvs = sorted([x.pv for x in self.from_versions])
                to_pvs = sorted([x.pv for x in self.to_versions])
                return (from_pvs != to_pvs)
        class BranchComparisonVersionResult:
            def __init__(self, id, pv, srcrev):
                self.id = id
                self.pv = pv
                self.srcrev = srcrev
            def version_expr(self):
                return (self.pv, self.srcrev)

        def map_name(recipe):
            pn = recipe.pn
            if pn.startswith('gcc-source-'):
                pn = pn.replace('-%s' % recipe.pv, '')
            elif pn.endswith(('-i586', '-i686')):
                pn = pn[:-5]
            elif pn.endswith('-x86_64-oesdk-linux'):
                pn = pn[:-19]
            return pn

        from_recipes = Recipe.objects.filter(layerbranch__branch=from_branch)
        to_recipes = Recipe.objects.filter(layerbranch__branch=to_branch)
        if layer_ids:
            from_recipes = from_recipes.filter(layerbranch__layer__in=layer_ids)
            to_recipes = to_recipes.filter(layerbranch__layer__in=layer_ids)
        recipes = {}
        for recipe in from_recipes:
            pn = map_name(recipe)
            res = recipes.get(pn, None)
            if not res:
                res = BranchComparisonResult(pn, recipe.short_desc)
                recipes[pn] = res
            res.from_versions.append(BranchComparisonVersionResult(id=recipe.id, pv=recipe.pv, srcrev=recipe.srcrev))
        for recipe in to_recipes:
            pn = map_name(recipe)
            res = recipes.get(pn, None)
            if not res:
                res = BranchComparisonResult(pn, recipe.short_desc)
                recipes[pn] = res
            res.to_versions.append(BranchComparisonVersionResult(id=recipe.id, pv=recipe.pv, srcrev=recipe.srcrev))

        added = []
        changed = []
        removed = []
        for _, recipe in sorted(recipes.items(), key=lambda item: item[0]):
            recipe.from_versions = sorted(recipe.from_versions, key=lambda item: LooseVersion(item.pv))
            from_version_exprs = [x.version_expr() for x in recipe.from_versions]
            recipe.to_versions = sorted(recipe.to_versions, key=lambda item: LooseVersion(item.pv))
            to_version_exprs = [x.version_expr() for x in recipe.to_versions]
            if not from_version_exprs:
                added.append(recipe)
            elif not to_version_exprs:
                recipe.id = recipe.from_versions[-1].id
                removed.append(recipe)
            elif from_version_exprs != to_version_exprs:
                changed.append(recipe)
        return added, changed, removed

    def form_valid(self, form):
        return HttpResponseRedirect(reverse_lazy('branch_comparison', args=(form.cleaned_data['from_branch'].name, form.cleaned_data['to_branch'].name)))

    def get_initial(self):
        initial = super(BranchCompareView, self).get_initial()
        from_branch_id = self.request.GET.get('from_branch', None)
        if from_branch_id is not None:
            initial['from_branch'] = get_object_or_404(Branch, id=from_branch_id)
        to_branch_id = self.request.GET.get('to_branch', None)
        if to_branch_id is not None:
            initial['to_branch'] = get_object_or_404(Branch, id=to_branch_id)
        initial['layers'] = self.request.GET.get('layers', str(LayerItem.objects.get(name=settings.CORE_LAYER_NAME).id))
        return initial

    def get_context_data(self, **kwargs):
        context = super(BranchCompareView, self).get_context_data(**kwargs)
        from_branch_id = self.request.GET.get('from_branch', None)
        to_branch_id = self.request.GET.get('to_branch', None)

        layer_ids = self.request.GET.get('layers', str(LayerItem.objects.get(name=settings.CORE_LAYER_NAME).id))
        from_branch = None
        if from_branch_id is not None:
            from_branch = get_object_or_404(Branch, id=from_branch_id)
        context['from_branch'] = from_branch
        to_branch = None
        if from_branch_id is not None:
            to_branch = get_object_or_404(Branch, id=to_branch_id)
        context['to_branch'] = to_branch
        if from_branch and to_branch:
            context['added'], context['changed'], context['removed'] = self.get_recipes(from_branch, to_branch, layer_ids)
        context['this_url_name'] = resolve(self.request.path_info).url_name
        context['layers'] = LayerItem.objects.filter(status__in=['P', 'X']).order_by('name')
        context['showlayers'] = layer_ids
        layerlist = dict(context['layers'].values_list('id', 'name'))
        context['showlayers_text'] = ', '.join([layerlist[int(i)] for i in layer_ids])

        return context


class RecipeDependenciesView(FormView):
    form_class = RecipeDependenciesForm

    def get_recipes(self, layerbranch, exclude_layer_ids, crosslayer):
        class RecipeResult:
            def __init__(self, id, pn, short_desc, license):
                self.id = id
                self.pn = pn
                self.short_desc = short_desc
                self.license = license
                self.deps = []
        class RecipeDependencyResult:
            def __init__(self, id, depname, pn, pv, license, layer, dynamic):
                self.id = id
                self.depname = depname
                self.pn = pn
                self.pv = pv
                self.license = license
                self.layer = layer
                self.dynamic = dynamic

        recipes = Recipe.objects.filter(layerbranch=layerbranch)

        layerprovides = []
        if crosslayer:
            layerprovides = list(ExtendedProvide.objects.filter(recipes__layerbranch=layerbranch).values_list('name', flat=True))

        branch = layerbranch.branch

        def process(resultobj, depname, dynamic):
            if crosslayer and depname in layerprovides:
                return
            eprovides = ExtendedProvide.objects.filter(name=depname)
            if eprovides:
                for eprovide in eprovides:
                    deprecipes = eprovide.recipes.filter(layerbranch__branch=branch).values('id', 'pn', 'pv', 'license', 'layerbranch__layer__name').order_by('-layerbranch__layer__index_preference', 'layerbranch', 'pn')
                    if exclude_layer_ids:
                        deprecipes = deprecipes.exclude(layerbranch__layer__in=exclude_layer_ids)
                    for deprecipe in deprecipes:
                        resultobj.deps.append(RecipeDependencyResult(deprecipe['id'],
                                                            depname,
                                                            deprecipe['pn'],
                                                            deprecipe['pv'],
                                                            deprecipe['license'],
                                                            deprecipe['layerbranch__layer__name'],
                                                            dynamic))
            if not resultobj.deps:
                resultobj.deps.append(RecipeDependencyResult(-1,
                                                    depname,
                                                    depname,
                                                    '',
                                                    '',
                                                    '',
                                                    dynamic))

        outrecipes = []
        for recipe in recipes:
            res = RecipeResult(recipe.id, recipe.pn, recipe.short_desc, recipe.license)
            for rdepname in recipe.staticbuilddep_set.values_list('name', flat=True).order_by('name'):
                process(res, rdepname, False)
            for rdepname in recipe.dynamicbuilddep_set.values_list('name', flat=True).order_by('name'):
                process(res, rdepname, True)
            outrecipes.append(res)

        return outrecipes

    def form_valid(self, form):
        return HttpResponseRedirect(reverse_lazy('recipe_deps', args=(form.cleaned_data['branch'].name)))

    def get_initial(self):
        initial = super(RecipeDependenciesView, self).get_initial()
        branch_id = self.request.GET.get('branch', None)
        if branch_id is not None:
            initial['branch'] = get_object_or_404(Branch, id=branch_id)
        layer_id = self.request.GET.get('layer', None)
        if layer_id is not None:
            initial['layer'] = get_object_or_404(LayerItem, id=layer_id)
        initial['excludelayers'] = self.request.GET.get('excludelayers', '')
        initial['crosslayer'] = self.request.GET.get('crosslayer', False)
        return initial

    def get_context_data(self, **kwargs):
        context = super(RecipeDependenciesView, self).get_context_data(**kwargs)
        branch_id = self.request.GET.get('branch', None)
        layer_id = self.request.GET.get('layer', None)
        exclude_layer_ids = self.request.GET.get('excludelayers', '')
        if exclude_layer_ids:
            exclude_layer_ids = exclude_layer_ids.split(',')
        branch = None
        if branch_id is not None:
            branch = get_object_or_404(Branch, id=branch_id)
        context['branch'] = branch
        layer = None
        if layer_id is not None:
            layer = get_object_or_404(LayerItem, id=layer_id)
        context['layer'] = layer
        crosslayer = self.request.GET.get('crosslayer', False)
        context['crosslayer'] = crosslayer
        layerbranch = None
        if layer:
            layerbranch = layer.get_layerbranch(branch.name)
        if layerbranch:
            context['recipes'] = self.get_recipes(layerbranch, exclude_layer_ids, crosslayer)
        context['this_url_name'] = resolve(self.request.path_info).url_name
        context['layers'] = LayerItem.objects.filter(status__in=['P', 'X']).order_by('name')
        context['excludelayers'] = exclude_layer_ids
        layerlist = dict(context['layers'].values_list('id', 'name'))
        context['excludelayers_text'] = ', '.join([layerlist[int(i)] for i in exclude_layer_ids])

        return context

