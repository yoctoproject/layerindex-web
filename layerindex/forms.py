# layerindex-web - form definitions
#
# Copyright (C) 2013, 2016-2019 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import re
from collections import OrderedDict

from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.validators import EmailValidator, RegexValidator, URLValidator
from django.forms.models import inlineformset_factory, modelformset_factory
from django_registration.forms import RegistrationForm
from django_registration.validators import (DEFAULT_RESERVED_NAMES,
                                            ReservedNameValidator,
                                            validate_confusables)

import settings
from layerindex.models import (Branch, ClassicRecipe,
                               LayerBranch, LayerItem, LayerMaintainer,
                               LayerNote, RecipeChange, RecipeChangeset,
                               SecurityQuestion, UserProfile, PatchDisposition)


class StyledForm(forms.Form):
    # Ensure form-control class for Bootstrap 3 is applied to Django-generated widgets
    def __init__(self, *args, **kwargs):
        super(StyledForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'

class StyledModelForm(forms.ModelForm):
    # Ensure form-control class for Bootstrap 3 is applied to Django-generated widgets
    def __init__(self, *args, **kwargs):
        super(StyledModelForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'


class LayerMaintainerForm(StyledModelForm):
    class Meta:
        model = LayerMaintainer
        fields = ('name', 'email', 'responsibility', 'status')

    def __init__(self, *args, **kwargs):
        super(LayerMaintainerForm, self).__init__(*args, **kwargs)
        if not self.instance.pk:
            del self.fields['status']

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email:
            if len(email) < 7:
                raise forms.ValidationError('%s is not a valid email address' % email)
            val = EmailValidator()
            val(email)

        return email

class BaseLayerMaintainerFormSet(forms.models.BaseInlineFormSet):
    def _construct_form(self, i, **kwargs):
        f = super(BaseLayerMaintainerFormSet, self)._construct_form(i, **kwargs)
        # Ensure the first form in the formset gets filled in
        if i == 0:
            f.empty_permitted = False
            f.required = True
        return f

LayerMaintainerFormSet = inlineformset_factory(LayerBranch, LayerMaintainer, form=LayerMaintainerForm, formset=BaseLayerMaintainerFormSet,  can_delete=False, extra=10, max_num=10)

class EditLayerForm(StyledModelForm):
    # Additional form fields
    vcs_subdir = forms.CharField(label='Repository subdirectory', max_length=40, required=False, help_text='Subdirectory within the repository where the layer is located, if not in the root (usually only used if the repository contains more than one layer)')
    deps = forms.ModelMultipleChoiceField(label='Other layers this layer depends upon', queryset=LayerItem.objects.filter(comparison=False), required=False)
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})

    class Meta:
        model = LayerItem
        fields = ('name', 'layer_type', 'summary', 'description', 'vcs_url', 'vcs_web_url', 'vcs_web_tree_base_url', 'vcs_web_file_base_url', 'vcs_web_commit_url', 'usage_url', 'mailing_list_url')

    def __init__(self, user, layerbranch, allow_base_type, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.layerbranch = layerbranch
        if self.instance.pk:
            self.fields['deps'].initial = [d.dependency.pk for d in self.layerbranch.dependencies_set.all()]
            del self.fields['captcha']
        else:
            self.fields['deps'].initial = [l.pk for l in LayerItem.objects.filter(name=settings.CORE_LAYER_NAME)]
            if user.is_authenticated:
                del self.fields['captcha']
        # Ensure repo subdir appears after repo URL
        field_order = list(self.fields.keys())
        field_order.pop(field_order.index('vcs_subdir'))
        name_pos = field_order.index('vcs_url') + 1
        field_order.insert(name_pos, 'vcs_subdir')
        new_fields = OrderedDict()
        for field in field_order:
            new_fields[field] = self.fields[field]
        self.fields = new_fields
        self.fields['vcs_subdir'].initial = layerbranch.vcs_subdir
        self.was_saved = False
        self.allow_base_type = allow_base_type

    def checked_deps(self):
        val = [int(v) for v in self['deps'].value()]
        return val

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if re.compile(r'[^a-z0-9-]').search(name):
            raise forms.ValidationError("Name must only contain alphanumeric characters and dashes")
        if name.startswith('-'):
            raise forms.ValidationError("Name must not start with a dash")
        if name.endswith('-'):
            raise forms.ValidationError("Name must not end with a dash")
        if '--' in name:
            raise forms.ValidationError("Name cannot contain consecutive dashes")
        return name

    def clean_summary(self):
        # Compress whitespace and use only spaces
        summary = self.cleaned_data['summary'].strip()
        summary = re.sub('\s+', ' ', summary)
        return summary

    def clean_layer_type(self):
        layer_type = self.cleaned_data['layer_type']
        if layer_type == 'A' and not self.allow_base_type:
            raise forms.ValidationError("Base type is not allowed, please select a more specific type")
        return layer_type

    def clean_description(self):
        description = self.cleaned_data['description'].strip()
        return description

    def clean_vcs_url(self):
        url = self.cleaned_data['vcs_url'].strip()
        val = RegexValidator(regex=r'^[a-z]+://[^ ]+$', message='Please enter a valid repository URL, e.g. git://server.name/path')
        val(url)
        return url

    def clean_vcs_subdir(self):
        subdir = self.cleaned_data['vcs_subdir'].strip()
        if subdir.endswith('/'):
            subdir = subdir[:-1]
        return subdir

    def clean_vcs_web_tree_base_url(self):
        url = self.cleaned_data['vcs_web_tree_base_url'].strip()
        if url:
            val = URLValidator()
            val(url)
        return url

    def clean_vcs_web_file_base_url(self):
        url = self.cleaned_data['vcs_web_file_base_url'].strip()
        if url:
            val = URLValidator()
            val(url)
        return url

    def clean_vcs_web_commit_url(self):
        url = self.cleaned_data['vcs_web_commit_url'].strip()
        if url:
            val = URLValidator()
            val(url)
        return url

    def clean_usage_url(self):
        usage = self.cleaned_data['usage_url'].strip()
        if usage.startswith('http'):
            val = URLValidator()
            val(usage)
        return usage


class EditNoteForm(StyledModelForm):
    class Meta:
        model = LayerNote
        fields = ('text',)

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        return text


class EditProfileForm(StyledModelForm):
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})
    security_question_1 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_1 = forms.CharField(widget=forms.TextInput(), label='Answer', initial="*****")
    security_question_2 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_2 = forms.CharField(widget=forms.TextInput(), label='Answer', initial="*****")
    security_question_3 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_3 = forms.CharField(widget=forms.TextInput(), label='Answer', initial="*****")

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'captcha')

    def __init__(self, *args, **kwargs):
        super(EditProfileForm, self ).__init__(*args, **kwargs)
        for field in ['captcha', 'security_question_1', 'security_question_2', 'security_question_3', 'answer_1', 'answer_2', 'answer_3']:
            self.fields[field].widget.attrs.update({
                'autocomplete': 'off'
            })
        user = kwargs.get("instance")
        try:
            self.fields['security_question_1'].initial=user.userprofile.securityquestionanswer_set.all()[0].security_question
            self.fields['security_question_2'].initial=user.userprofile.securityquestionanswer_set.all()[1].security_question
            self.fields['security_question_3'].initial=user.userprofile.securityquestionanswer_set.all()[2].security_question
        except UserProfile.DoesNotExist:
            # The super user won't have had security questions created already
            self.fields['security_question_1'].initial=SecurityQuestion.objects.all()[0]
            self.fields['security_question_2'].initial=SecurityQuestion.objects.all()[1]
            self.fields['security_question_3'].initial=SecurityQuestion.objects.all()[2]
            pass

    def clean_username(self):
        username = self.cleaned_data['username']
        if 'username' in self.changed_data:
            key = 'username_attempts_%s' % self.instance.username
            attempt = cache.get(key) or 0
            if attempt < 10:
                try:
                    reserved_validator = ReservedNameValidator(
                        reserved_names=DEFAULT_RESERVED_NAMES
                    )
                    reserved_validator(username)
                    validate_confusables(username)
                except forms.ValidationError as v:
                    self.add_error('username', v)

                attempt += 1
                cache.set(key, attempt, 300)
            else:
                raise forms.ValidationError('Maximum username change attempts exceeded')

        return username

    def clean(self):
        cleaned_data = super(EditProfileForm, self).clean()
        for data in self.changed_data:
            # Check if a security answer has been updated. If one is updated, they must all be
            # and each security question must be unique.
            if 'answer' in data:
                if 'answer_1' not in self.changed_data \
                  or 'answer_2' not in self.changed_data \
                  or 'answer_3' not in self.changed_data:
                    raise forms.ValidationError("Please provide answers for all three security questions.")
                security_question_1 = self.cleaned_data["security_question_1"]
                security_question_2 = self.cleaned_data["security_question_2"]
                security_question_3 = self.cleaned_data["security_question_3"]
                if security_question_1 == security_question_2:
                    raise forms.ValidationError({'security_question_2': ["Questions may only be chosen once."]})
                if security_question_1 == security_question_3 or security_question_2 == security_question_3:
                    raise forms.ValidationError({'security_question_3': ["Questions may only be chosen once."]})
        return cleaned_data


class ClassicRecipeForm(StyledModelForm):
    class Meta:
        model = ClassicRecipe
        fields = ('cover_layerbranch', 'cover_pn', 'cover_status', 'cover_verified', 'cover_comment', 'classic_category', 'needs_attention')

    def clean(self):
        cleaned_data = super(ClassicRecipeForm, self).clean()
        cover_pn = cleaned_data.get('cover_pn')
        cover_layerbranch = cleaned_data.get('cover_layerbranch')
        if cleaned_data.get('cover_status') in ['U', 'N', 'S']:
            if cover_layerbranch:
                cleaned_data['cover_layerbranch'] = None
            if cover_pn:
                cleaned_data['cover_pn'] = ''
        return cleaned_data


class AdvancedRecipeSearchForm(StyledForm):
    FIELD_CHOICES = (
        ('pn',          'Name'),
        ('summary',     'Summary'),
        ('description', 'Description'),
        ('homepage',    'Homepage'),
        ('bugtracker',  'Bug tracker'),
        ('section',     'Section'),
        ('license',     'License'),
    )
    MATCH_TYPE_CHOICES = (
        ('C', 'contains'),
        ('N', 'does not contain'),
        ('E', 'equals'),
        ('B', 'is blank'),
    )
    field = forms.ChoiceField(choices=FIELD_CHOICES)
    match_type = forms.ChoiceField(choices=MATCH_TYPE_CHOICES)
    value = forms.CharField(max_length=255, required=False)
    layer = forms.ModelChoiceField(queryset=LayerItem.objects.filter(comparison=False).filter(status__in=['P', 'X']).order_by('name'), empty_label="(any)", required=False)


class RecipeChangesetForm(StyledModelForm):
    class Meta:
        model = RecipeChangeset
        fields = ('name',)


class BulkChangeEditForm(StyledModelForm):
    class Meta:
        model = RecipeChange
        fields = ('summary', 'description', 'homepage', 'bugtracker', 'section', 'license')

BulkChangeEditFormSet = modelformset_factory(RecipeChange, form=BulkChangeEditForm, extra=0)


class ClassicRecipeSearchForm(StyledForm):
    COVER_STATUS_CHOICES = [('','(any)'), ('!','(unknown / not available)'), ('#','(available)')] + ClassicRecipe.COVER_STATUS_CHOICES
    VERIFIED_CHOICES = [
        ('', '(any)'),
        ('1', 'Verified'),
        ('0', 'Unverified'),
        ]
    PATCH_CHOICES = [
        ('', '(any)'),
        ('1', 'Has patches'),
        ('0', 'No patches'),
        ]
    ATTENTION_CHOICES = [
        ('', '(any)'),
        ('1', 'Yes'),
        ('0', 'No'),
        ]

    q = forms.CharField(label='Keyword', max_length=255, required=False)
    category = forms.CharField(max_length=255, required=False)
    oe_layer = forms.ModelChoiceField(label='OE Layer', queryset=LayerItem.objects.filter(comparison=False).filter(status__in=['P', 'X']).order_by('name'), empty_label="(any)", required=False)
    has_patches = forms.ChoiceField(label='Patches', choices=PATCH_CHOICES, required=False)
    cover_status = forms.ChoiceField(label='Status', choices=COVER_STATUS_CHOICES, required=False)
    cover_verified = forms.ChoiceField(label='Verified', choices=VERIFIED_CHOICES, required=False)
    needs_attention = forms.ChoiceField(label='Needs attention', choices=ATTENTION_CHOICES, required=False)


class ComparisonRecipeSelectForm(StyledForm):
    q = forms.CharField(label='Keyword', max_length=255, required=False)
    oe_layer = forms.ModelChoiceField(label='OE Layer', queryset=LayerItem.objects.filter(comparison=False).filter(status__in=['P', 'X']).order_by('name'), empty_label="(any)", required=False)


class PatchDispositionForm(StyledModelForm):
    class Meta:
        model = PatchDisposition
        fields = ('patch', 'disposition', 'comment')
        widgets = {
            'patch': forms.HiddenInput(),
        }

PatchDispositionFormSet = modelformset_factory(PatchDisposition, form=PatchDispositionForm, extra=0)


class BranchComparisonForm(StyledForm):
    from_branch = forms.ModelChoiceField(label='From', queryset=Branch.objects.none())
    to_branch = forms.ModelChoiceField(label='To', queryset=Branch.objects.none())
    layers = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, request=None, **kwargs):
        super(BranchComparisonForm, self).__init__(*args, **kwargs)
        qs = Branch.objects.filter(comparison=False, hidden=False).order_by('sort_priority', 'name')
        self.fields['from_branch'].queryset = qs
        self.fields['to_branch'].queryset = qs
        self.request = request

    def clean(self):
        cleaned_data = super(BranchComparisonForm, self).clean()
        if cleaned_data['from_branch'] == cleaned_data['to_branch']:
            raise forms.ValidationError({'to_branch': 'From and to branches cannot be the same'})
        return cleaned_data


class RecipeDependenciesForm(StyledForm):
    branch = forms.ModelChoiceField(label='Branch', queryset=Branch.objects.none())
    layer = forms.ModelChoiceField(queryset=LayerItem.objects.filter(comparison=False).filter(status__in=['P', 'X']).order_by('name'), required=True)
    crosslayer = forms.BooleanField(required=False)
    excludelayers = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, request=None, **kwargs):
        super(RecipeDependenciesForm, self).__init__(*args, **kwargs)
        qs = Branch.objects.filter(comparison=False, hidden=False).order_by('sort_priority', 'name')
        self.fields['branch'].queryset = qs
        self.request = request
