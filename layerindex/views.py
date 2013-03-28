# layerindex-web - view definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.template import RequestContext
from layerindex.models import Branch, LayerItem, LayerMaintainer, LayerBranch, LayerDependency, LayerNote, Recipe, Machine
from datetime import datetime
from django.views.generic import DetailView, ListView
from layerindex.forms import EditLayerForm, LayerMaintainerFormSet, EditNoteForm
from django.db import transaction
from django.contrib.auth.models import User, Permission
from django.db.models import Q
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.template import Context
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
import simplesearch
import settings


def edit_layernote_view(request, template_name, slug, pk=None):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if not (request.user.is_authenticated() and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
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
    if not (request.user.is_authenticated() and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
        raise PermissionDenied
    layernote = get_object_or_404(LayerNote, pk=pk)
    if request.method == 'POST':
        layernote.delete()
        return HttpResponseRedirect(layeritem.get_absolute_url())
    else:
        return render(request, template_name, {
            'object': layernote,
            'object_type': layernote._meta.verbose_name,
            'return_url': layeritem.get_absolute_url()
        })

def delete_layer_view(request, template_name, slug):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if not (request.user.is_authenticated() and request.user.has_perm('layerindex.publish_layer') and layeritem.status == 'N'):
        raise PermissionDenied
    if request.method == 'POST':
        layeritem.delete()
        return HttpResponseRedirect(reverse('layer_list'))
    else:
        return render(request, template_name, {
            'object': layeritem,
            'object_type': layeritem._meta.verbose_name,
            'return_url': layeritem.get_absolute_url()
        })

def edit_layer_view(request, template_name, slug=None):
    if slug:
        # Edit mode
        branch = Branch.objects.filter(name=request.session.get('branch', 'master'))[:1].get()
        layeritem = get_object_or_404(LayerItem, name=slug)
        if not (request.user.is_authenticated() and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
            raise PermissionDenied
        layerbranch = get_object_or_404(LayerBranch, layer=layeritem, branch=branch)
        deplistlayers = LayerItem.objects.exclude(id=layeritem.id).order_by('name')
    else:
        # Submit mode
        branch = Branch.objects.filter(name='master')[:1].get()
        layeritem = LayerItem()
        layerbranch = LayerBranch(layer=layeritem, branch=branch)
        deplistlayers = LayerItem.objects.all().order_by('name')

    if request.method == 'POST':
        last_vcs_url = layeritem.vcs_url
        form = EditLayerForm(request.user, layerbranch, request.POST, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(request.POST, instance=layerbranch)
        if form.is_valid() and maintainerformset.is_valid():
            with transaction.commit_on_success():
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
                        d = Context({
                            'user_name': user.get_full_name(),
                            'layer_name': layeritem.name,
                            'layer_url': request.build_absolute_uri(reverse('layer_review', args=(layeritem.name,))) + '?branch=master',
                        })
                        subject = '%s - %s' % (settings.SUBMIT_EMAIL_SUBJECT, layeritem.name)
                        from_email = settings.SUBMIT_EMAIL_FROM
                        to_email = user.email
                        text_content = plaintext.render(d)
                        msg = EmailMessage(subject, text_content, from_email, [to_email])
                        msg.send()
                    return HttpResponseRedirect(reverse('submit_layer_thanks'))
            form.was_saved = True
    else:
        form = EditLayerForm(request.user, layerbranch, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(instance=layerbranch)

    return render(request, template_name, {
        'form': form,
        'maintainerformset': maintainerformset,
        'deplistlayers': deplistlayers,
    })

def _check_branch(request):
    branchname = request.GET.get('branch', '')
    if branchname:
        branch = get_object_or_404(Branch, name=branchname)
        request.session['branch'] = branch.name

def switch_branch_view(request, slug):
    branch = get_object_or_404(Branch, name=slug)
    request.session['branch'] = branch.name
    return_url = request.META.get('HTTP_REFERER')
    if not return_url:
        return_url = reverse('layer_list')
    return HttpResponseRedirect(return_url)

def publish(request, name):
    if not (request.user.is_authenticated() and request.user.has_perm('layerindex.publish_layer')):
        raise PermissionDenied
    return _statuschange(request, name, 'P')

def _statuschange(request, name, newstatus):
    w = get_object_or_404(LayerItem, name=name)
    if w.status != newstatus:
        w.change_status(newstatus, request.user.username)
        w.save()
    return HttpResponseRedirect(w.get_absolute_url())

class LayerListView(ListView):
    context_object_name = 'layerbranch_list'

    def get_queryset(self):
        return LayerBranch.objects.filter(branch__name=self.request.session.get('branch', 'master')).filter(layer__status='P').order_by('layer__layer_type', 'layer__name')

    def get_context_data(self, **kwargs):
        context = super(LayerListView, self).get_context_data(**kwargs)
        context['layer_type_choices'] = LayerItem.LAYER_TYPE_CHOICES
        return context

class LayerReviewListView(ListView):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('layerindex.publish_layer'):
            raise PermissionDenied
        _check_branch(request)
        return super(LayerReviewListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return LayerBranch.objects.filter(branch__name=self.request.session.get('branch', 'master')).filter(layer__status='N').order_by('layer__name')

class LayerDetailView(DetailView):
    model = LayerItem
    slug_field = 'name'

    # This is a bit of a mess. Surely there has to be a better way to handle this...
    def dispatch(self, request, *args, **kwargs):
        _check_branch(request)
        self.user = request.user
        res = super(LayerDetailView, self).dispatch(request, *args, **kwargs)
        l = self.get_object()
        if l:
            if l.status == 'N':
                if not (request.user.is_authenticated() and request.user.has_perm('layerindex.publish_layer')):
                    raise PermissionDenied
        return res

    def get_context_data(self, **kwargs):
        context = super(LayerDetailView, self).get_context_data(**kwargs)
        layer = context['layeritem']
        context['useredit'] = layer.user_can_edit(self.user)
        context['layerbranch'] = layer.get_layerbranch(self.request.session.get('branch', 'master'))
        return context

class LayerReviewDetailView(LayerDetailView):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('layerindex.publish_layer'):
            raise PermissionDenied
        return super(LayerReviewDetailView, self).dispatch(request, *args, **kwargs)

class RecipeSearchView(ListView):
    context_object_name = 'recipe_list'
    paginate_by = 50

    def get_queryset(self):
        query_string = self.request.GET.get('q', '')
        init_qs = Recipe.objects.filter(layerbranch__branch__name=self.request.session.get('branch', 'master'))
        if query_string.strip():
            entry_query = simplesearch.get_query(query_string, ['pn', 'summary', 'description', 'filename'])
            qs = init_qs.filter(entry_query).order_by('pn', 'layerbranch__layer')
        else:
            if 'q' in self.request.GET:
                qs = init_qs.order_by('pn', 'layerbranch__layer')
            else:
                # It's a bit too slow to return all records by default, and most people
                # won't actually want that (if they do they can just hit the search button
                # with no query string)
                return Recipe.objects.none()

        # Add extra column so we can show "duplicate" recipes from other layers de-emphasised
        # (it's a bit crude having to do this using SQL but I couldn't find a better way...)
        return qs.extra(
            select={
                'preferred_count': """SELECT COUNT(1)
FROM layerindex_recipe AS recipe2
, layerindex_layerbranch as branch2
, layerindex_layeritem as layer2
WHERE branch2.id = recipe2.layerbranch_id
AND layer2.id = branch2.layer_id
AND layer2.layer_type in ('S', 'A')
AND recipe2.pn = layerindex_recipe.pn
AND recipe2.layerbranch_id < layerindex_recipe.layerbranch_id
"""
            },
        )

    def get_context_data(self, **kwargs):
        context = super(RecipeSearchView, self).get_context_data(**kwargs)
        context['search_keyword'] = self.request.GET.get('q', '')
        return context

class MachineSearchView(ListView):
    context_object_name = 'machine_list'
    paginate_by = 50

    def get_queryset(self):
        query_string = self.request.GET.get('q', '')
        init_qs = Machine.objects.filter(layerbranch__branch__name=self.request.session.get('branch', 'master'))
        if query_string.strip():
            entry_query = simplesearch.get_query(query_string, ['name', 'description'])
            return init_qs.filter(entry_query).order_by('name', 'layerbranch__layer')
        else:
            return init_qs.order_by('name', 'layerbranch__layer')

    def get_context_data(self, **kwargs):
        context = super(MachineSearchView, self).get_context_data(**kwargs)
        context['search_keyword'] = self.request.GET.get('q', '')
        return context


class PlainTextListView(ListView):
    def render_to_response(self, context):
        "Returns a plain text response rendering of the template"
        template = get_template(self.template_name)
        return HttpResponse(template.render(Context(context)),
                                 content_type='text/plain')
