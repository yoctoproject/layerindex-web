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
from layerindex.models import LayerItem, LayerMaintainer, LayerDependency, LayerNote, Recipe, Machine
from datetime import datetime
from django.views.generic import DetailView, ListView
from layerindex.forms import SubmitLayerForm, LayerMaintainerFormSet, EditNoteForm
from django.db import transaction
from django.contrib.auth.models import User, Permission
from django.db.models import Q
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.template import Context
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
        layeritem = get_object_or_404(LayerItem, name=slug)
        if not (request.user.is_authenticated() and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
            raise PermissionDenied
    else:
        # Submit mode
        layeritem = LayerItem()

    if request.method == 'POST':
        form = SubmitLayerForm(request.user, request.POST, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(request.POST, instance=layeritem)
        if form.is_valid() and maintainerformset.is_valid():
            with transaction.commit_on_success():
                form.save()
                maintainerformset.save()
                if slug:
                    new_deps = form.cleaned_data['deps']
                    existing_deps = [deprec.dependency for deprec in layeritem.dependencies_set.all()]
                    for dep in new_deps:
                        if dep not in existing_deps:
                            deprec = LayerDependency()
                            deprec.layer = layeritem
                            deprec.dependency = dep
                            deprec.save()
                    for dep in existing_deps:
                        if dep not in new_deps:
                            layeritem.dependencies_set.filter(dependency=dep).delete()
                else:
                    # Save dependencies
                    for dep in form.cleaned_data['deps']:
                        deprec = LayerDependency()
                        deprec.layer = layeritem
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
                            'layer_url': request.build_absolute_uri(layeritem.get_absolute_url()),
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
        form = SubmitLayerForm(request.user, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(instance=layeritem)

    return render(request, template_name, {
        'form': form,
        'maintainerformset': maintainerformset,
        'deplistlayers': LayerItem.objects.all().order_by('name'),
    })

def submit_layer_thanks(request):
    return render(request, 'layerindex/submitthanks.html')

def about(request):
    return render(request, 'layerindex/about.html')

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
    context_object_name = 'layer_list'

    def get_queryset(self):
        return LayerItem.objects.filter(status__in=self.request.session.get('status_filter', 'P')).order_by('name')

    def get_context_data(self, **kwargs):
        context = super(LayerListView, self).get_context_data(**kwargs)
        context['layer_type_choices'] = LayerItem.LAYER_TYPE_CHOICES
        return context

class LayerDetailView(DetailView):
    model = LayerItem
    slug_field = 'name'

    # This is a bit of a mess. Surely there has to be a better way to handle this...
    def dispatch(self, request, *args, **kwargs):
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
        return context

class RecipeSearchView(ListView):
    context_object_name = 'recipe_list'
    paginate_by = 50

    def get_queryset(self):
        query_string = self.request.GET.get('q', '')
        if query_string.strip():
            entry_query = simplesearch.get_query(query_string, ['pn', 'summary', 'description', 'filename'])
            return Recipe.objects.filter(entry_query).order_by('pn', 'layer')
        else:
            return Recipe.objects.all().order_by('pn', 'layer')

    def get_context_data(self, **kwargs):
        context = super(RecipeSearchView, self).get_context_data(**kwargs)
        context['search_keyword'] = self.request.GET.get('q', '')
        return context

class MachineSearchView(ListView):
    context_object_name = 'machine_list'
    paginate_by = 50

    def get_queryset(self):
        query_string = self.request.GET.get('q', '')
        if query_string.strip():
            entry_query = simplesearch.get_query(query_string, ['name', 'description'])
            return Machine.objects.filter(entry_query).order_by('name', 'layer')
        else:
            return Machine.objects.all().order_by('name', 'layer')

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
