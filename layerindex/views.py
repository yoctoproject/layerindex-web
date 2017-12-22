# layerindex-web - view definitions
#
# Copyright (C) 2013-2016 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
from django.shortcuts import get_object_or_404, get_list_or_404, render
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.core.urlresolvers import reverse, reverse_lazy, resolve
from django.core.exceptions import PermissionDenied
from django.template import RequestContext
from layerindex.models import Branch, LayerItem, LayerMaintainer, LayerBranch, LayerDependency, LayerNote, Update, LayerUpdate, Recipe, Machine, Distro, BBClass, BBAppend, RecipeChange, RecipeChangeset, ClassicRecipe, StaticBuildDep, DynamicBuildDep
from datetime import datetime
from django.views.generic import TemplateView, DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.base import RedirectView
from layerindex.forms import EditLayerForm, LayerMaintainerFormSet, EditNoteForm, EditProfileForm, RecipeChangesetForm, AdvancedRecipeSearchForm, BulkChangeEditFormSet, ClassicRecipeForm, ClassicRecipeSearchForm
from django.db import transaction
from django.contrib.auth.models import User, Permission
from django.db.models import Q, Count, Sum
from django.template.loader import get_template
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from reversion.models import Revision
from . import utils
from . import simplesearch
from . import tasks
import settings
from django.dispatch import receiver
import reversion
from django.db.models.signals import pre_save

def edit_layernote_view(request, template_name, slug, pk=None):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if layeritem.classic:
        raise Http404
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
    if layeritem.classic:
        raise Http404
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
            'cancel_url': layeritem.get_absolute_url()
        })

def delete_layer_view(request, template_name, slug):
    layeritem = get_object_or_404(LayerItem, name=slug)
    if layeritem.classic:
        raise Http404
    if not (request.user.is_authenticated() and request.user.has_perm('layerindex.publish_layer') and layeritem.status == 'N'):
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
        if layeritem.classic:
            raise Http404
        if not (request.user.is_authenticated() and (request.user.has_perm('layerindex.publish_layer') or layeritem.user_can_edit(request.user))):
            raise PermissionDenied
        layerbranch = get_object_or_404(LayerBranch, layer=layeritem, branch=branchobj)
        deplistlayers = LayerItem.objects.exclude(id=layeritem.id).order_by('name')
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
        deplistlayers = LayerItem.objects.filter(classic=False).order_by('name')

    if request.method == 'POST':
        last_vcs_url = layeritem.vcs_url
        form = EditLayerForm(request.user, layerbranch, request.POST, instance=layeritem)
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
            messages.success(request, 'Layer %s saved successfully.' % layeritem.name)
            if return_url:
                if returnto == 'layer_review':
                    return_url = reverse_lazy(returnto, args=(layeritem.name,))
                else:
                    return_url = reverse_lazy(returnto, args=(branch, layeritem.name))
                return HttpResponseRedirect(return_url)
    else:
        form = EditLayerForm(request.user, layerbranch, instance=layeritem)
        maintainerformset = LayerMaintainerFormSet(instance=layerbranch)

    return render(request, template_name, {
        'form': form,
        'maintainerformset': maintainerformset,
        'deplistlayers': deplistlayers,
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
    import os
    import os.path
    changeset = get_object_or_404(RecipeChangeset, pk=pk)
    # FIXME this couples the web server and machine running the update script together,
    # but given that it's a separate script the way is open to decouple them in future
    try:
        ret = utils.runcmd('%s bulkchange.py %d %s' % (sys.executable, int(pk), settings.TEMP_BASE_DIR), os.path.dirname(__file__))
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

def publish_view(request, name):
    if not (request.user.is_authenticated() and request.user.has_perm('layerindex.publish_layer')):
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
        # find appropriate help contact
        help_contact = None
        for user in User.objects.all():
            if user.username != 'root' and (user.is_staff or user.is_superuser) and user.is_active:
                help_contact = user
                break

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
            'help_contact': help_contact,
        }
        body = bodytext.render(d)

        tasks.send_email.apply_async((subject, body, from_email, [m.email for m in maintainers]))

    return _statuschange(request, name, 'P')

def _statuschange(request, name, newstatus):
    w = get_object_or_404(LayerItem, name=name)
    if w.classic:
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
            if l.classic:
                raise Http404
            if l.status == 'N':
                if not (request.user.is_authenticated() and request.user.has_perm('layerindex.publish_layer')):
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
            context['updates'] = layerbranch.layerupdate_set.order_by('-started')
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

    def get_queryset(self):
        _check_url_branch(self.kwargs)
        query_string = self.request.GET.get('q', '')
        init_qs = Recipe.objects.filter(layerbranch__branch__name=self.kwargs['branch'])

        # Support slightly crude search on inherits field
        query_items = query_string.split()
        inherits = []
        query_terms = []
        for item in query_items:
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
                    if query_layer:
                        init_qs = init_qs.filter(
                            layerbranch__layer=query_layer[0])
                    else:
                        messages.add_message(self.request, messages.ERROR,
                                            'No layer \"%s\" was found.'
                                            % query_layername)
            else:
                query_terms.append(item)
        if inherits:
            # FIXME This is a bit ugly, perhaps we should consider having this as a one-many relationship instead
            for inherit in inherits:
                init_qs = init_qs.filter(Q(inherits=inherit) | Q(inherits__startswith=inherit + ' ') | Q(inherits__endswith=' ' + inherit) | Q(inherits__contains=' %s ' % inherit))
        query_string = ' '.join(query_terms)

        if query_string.strip():
            order_by = ('pn', 'layerbranch__layer')

            qs0 = init_qs.filter(pn=query_string).order_by(*order_by)
            qs0 = recipes_preferred_count(qs0)

            entry_query = simplesearch.get_query(query_string, ['pn'])
            qs1 = init_qs.filter(entry_query).order_by(*order_by)
            qs1 = recipes_preferred_count(qs1)

            entry_query = simplesearch.get_query(query_string, ['description', 'summary'])
            qs2 = init_qs.filter(entry_query).order_by(*order_by)
            qs2 = recipes_preferred_count(qs2)

            qs = list(utils.chain_unique(qs0, qs1, qs2))
        else:
            if 'q' in self.request.GET:
                qs = init_qs.order_by('pn', 'layerbranch__layer')
                qs = list(recipes_preferred_count(qs))
            else:
                # It's a bit too slow to return all records by default, and most people
                # won't actually want that (if they do they can just hit the search button
                # with no query string)
                return Recipe.objects.none()

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

    def get_context_data(self, **kwargs):
        layer_ids = [int(i) for i in self.request.GET.getlist('l')]
        context = super(DuplicatesView, self).get_context_data(**kwargs)
        context['recipes'] = self.get_recipes(layer_ids)
        context['classes'] = self.get_classes(layer_ids)
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
        if not self.request.user.is_authenticated():
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
        if not request.user.is_authenticated():
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
            entry_query = simplesearch.get_query(query_string, ['name', 'description'])
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
        return Update.objects.all().order_by('-started').annotate(errors=Sum('layerupdate__errors'), warnings=Sum('layerupdate__warnings'))


class UpdateDetailView(DetailView):
    model = Update

    def get_context_data(self, **kwargs):
        context = super(UpdateDetailView, self).get_context_data(**kwargs)
        update = self.get_object()
        if update:
            context['layerupdates'] = update.layerupdate_set.exclude(log__isnull=True).exclude(log__exact='')
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
            entry_query = simplesearch.get_query(query_string, ['name', 'description'])
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
            entry_query = simplesearch.get_query(query_string, ['name'])
            return init_qs.filter(entry_query).order_by('name', 'layerbranch__layer')

        if 'q' in self.request.GET:
            return init_qs.order_by('name', 'layerbranch__layer')

        # Be consistent with RecipeSearchView
        return Distro.objects.none()

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


class EditProfileFormView(UpdateView):
    form_class = EditProfileForm

    def dispatch(self, request, *args, **kwargs):
        self.user = request.user
        return super(EditProfileFormView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.user

    def get_success_url(self):
        return reverse('frontpage')


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
            #context['verappends'] = BBAppend.objects.filter(layerbranch__branch=recipe.layerbranch.branch).filter(filename='%s.bbappend' % verappendprefix)
            context['appends'] = BBAppend.objects.filter(layerbranch__branch=recipe.layerbranch.branch).filter(filename__regex=r'^%s(_[^_]*)?\.bbappend' % appendprefix)
            verappends = []
            for append in context['appends']:
                if append.matches_recipe(recipe):
                    verappends.append(append)
            context['verappends'] = verappends
            context['packageconfigs'] = recipe.packageconfig_set.order_by('feature')
            context['staticdependencies'] = recipe.staticbuilddep_set.order_by('name')
        return context


class ClassicRecipeSearchView(RecipeSearchView):
    def render_to_response(self, context, **kwargs):
        # Bypass the redirect-to-single-instance behaviour of RecipeSearchView
        return super(ListView, self).render_to_response(context, **kwargs)

    def get_queryset(self):
        self.kwargs['branch'] = 'oe-classic'
        query_string = self.request.GET.get('q', '')
        cover_status = self.request.GET.get('cover_status', None)
        cover_verified = self.request.GET.get('cover_verified', None)
        category = self.request.GET.get('category', None)
        init_qs = ClassicRecipe.objects.filter(layerbranch__branch__name='oe-classic')
        if cover_status:
            if cover_status == '!':
                init_qs = init_qs.filter(cover_status__in=['U', 'N'])
            else:
                init_qs = init_qs.filter(cover_status=cover_status)
        if cover_verified:
            init_qs = init_qs.filter(cover_verified=(cover_verified=='1'))
        if category:
            init_qs = init_qs.filter(classic_category__icontains=category)
        if query_string.strip():
            order_by = ('pn', 'layerbranch__layer')

            qs0 = init_qs.filter(pn=query_string).order_by(*order_by)

            entry_query = simplesearch.get_query(query_string, ['pn'])
            qs1 = init_qs.filter(entry_query).order_by(*order_by)

            entry_query = simplesearch.get_query(query_string, ['summary', 'description'])
            qs2 = init_qs.filter(entry_query).order_by(*order_by)

            qs = list(utils.chain_unique(qs0, qs1, qs2))
        else:
            if 'q' in self.request.GET:
                qs = init_qs.order_by('pn', 'layerbranch__layer')
            else:
                # It's a bit too slow to return all records by default, and most people
                # won't actually want that (if they do they can just hit the search button
                # with no query string)
                return Recipe.objects.none()
        return qs

    def get_context_data(self, **kwargs):
        context = super(ClassicRecipeSearchView, self).get_context_data(**kwargs)
        context['multi_classic_layers'] = LayerItem.objects.filter(classic=True).count() > 1
        if 'q' in self.request.GET:
            searched = True
            search_form = ClassicRecipeSearchForm(self.request.GET)
        else:
            searched = False
            search_form = ClassicRecipeSearchForm()
        context['search_form'] = search_form
        context['searched'] = searched
        return context



class ClassicRecipeDetailView(UpdateView):
    model = ClassicRecipe
    form_class = ClassicRecipeForm
    context_object_name = 'recipe'

    def _can_edit(self):
        if self.request.user.is_authenticated():
            if not self.request.user.has_perm('layerindex.edit_classic'):
                user_email = self.request.user.email.strip().lower()
                if not LayerMaintainer.objects.filter(email__iexact=user_email):
                    return False
        else:
            return False
        return True

    def post(self, request, *args, **kwargs):
        if not self._can_edit():
            raise PermissionDenied

        return super(ClassicRecipeDetailView, self).post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('classic_recipe_search')

    def get_context_data(self, **kwargs):
        context = super(ClassicRecipeDetailView, self).get_context_data(**kwargs)
        context['can_edit'] = self._can_edit()
        return context


class ClassicRecipeStatsView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super(ClassicRecipeStatsView, self).get_context_data(**kwargs)
        # *** Cover status chart ***
        statuses = []
        status_counts = {}
        for choice, desc in ClassicRecipe.COVER_STATUS_CHOICES:
            statuses.append(desc)
            status_counts[desc] = ClassicRecipe.objects.filter(cover_status=choice).count()
        statuses = sorted(statuses, key=lambda status: status_counts[status], reverse=True)
        chartdata = {'x': statuses, 'y': [status_counts[k] for k in statuses]}
        context['charttype_status'] = 'pieChart'
        context['chartdata_status'] = chartdata
        context['extra_status'] = {
            'x_is_date': False,
            'x_axis_format': '',
            'tag_script_js': True,
            'jquery_on_ready': False,
        }
        # *** Categories chart ***
        categories = ['obsoletedir', 'nonworkingdir']
        uniquevals = ClassicRecipe.objects.exclude(classic_category='').values_list('classic_category', flat=True).distinct()
        for value in uniquevals:
            cats = value.split()
            for cat in cats:
                if not cat in categories:
                    categories.append(cat)
        categories.append('none')
        catcounts = dict.fromkeys(categories, 0)
        unmigrated = ClassicRecipe.objects.filter(cover_status='U')
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
        chartdata_category = {'x': categories, 'y': [catcounts[k] for k in categories]}
        context['charttype_category'] = 'pieChart'
        context['chartdata_category'] = chartdata_category
        context['extra_category'] = {
            'x_is_date': False,
            'x_axis_format': '',
            'tag_script_js': True,
            'jquery_on_ready': False,
        }
        return context


class StatsView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super(StatsView, self).get_context_data(**kwargs)
        context['layercount'] = LayerItem.objects.count()
        context['recipe_count_distinct'] = Recipe.objects.values('pn').distinct().count()
        context['class_count_distinct'] = BBClass.objects.values('name').distinct().count()
        context['machine_count_distinct'] = Machine.objects.values('name').distinct().count()
        context['distro_count_distinct'] = Distro.objects.values('name').distinct().count()
        context['perbranch'] = Branch.objects.order_by('sort_priority').annotate(
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
