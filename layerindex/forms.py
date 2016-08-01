# layerindex-web - form definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from collections import OrderedDict
from layerindex.models import LayerItem, LayerBranch, LayerMaintainer, LayerNote, RecipeChangeset, RecipeChange, ClassicRecipe
from django import forms
from django.core.validators import URLValidator, RegexValidator, EmailValidator
from django.forms.models import inlineformset_factory, modelformset_factory
from captcha.fields import CaptchaField
from django.contrib.auth.models import User
import re
import settings


class LayerMaintainerForm(forms.ModelForm):
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

class EditLayerForm(forms.ModelForm):
    # Additional form fields
    vcs_subdir = forms.CharField(label='Repository subdirectory', max_length=40, required=False, help_text='Subdirectory within the repository where the layer is located, if not in the root (usually only used if the repository contains more than one layer)')
    deps = forms.ModelMultipleChoiceField(label='Other layers this layer depends upon', queryset=LayerItem.objects.filter(classic=False), required=False)
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})

    class Meta:
        model = LayerItem
        fields = ('name', 'layer_type', 'summary', 'description', 'vcs_url', 'vcs_web_url', 'vcs_web_tree_base_url', 'vcs_web_file_base_url', 'usage_url', 'mailing_list_url')

    def __init__(self, user, layerbranch, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.layerbranch = layerbranch
        if self.instance.pk:
            self.fields['deps'].initial = [d.dependency.pk for d in self.layerbranch.dependencies_set.all()]
            del self.fields['captcha']
        else:
            self.fields['deps'].initial = [l.pk for l in LayerItem.objects.filter(name=settings.CORE_LAYER_NAME)]
            if user.is_authenticated():
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

    def clean_description(self):
        description = self.cleaned_data['description'].strip()
        return description

    def clean_vcs_url(self):
        url = self.cleaned_data['vcs_url'].strip()
        val = RegexValidator(regex=r'[a-z]+://.*', message='Please enter a valid repository URL, e.g. git://server.name/path')
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

    def clean_usage_url(self):
        usage = self.cleaned_data['usage_url'].strip()
        if usage.startswith('http'):
            val = URLValidator()
            val(usage)
        return usage


class EditNoteForm(forms.ModelForm):
    class Meta:
        model = LayerNote
        fields = ('text',)

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        return text


class EditProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')


class ClassicRecipeForm(forms.ModelForm):
    class Meta:
        model = ClassicRecipe
        fields = ('cover_layerbranch', 'cover_pn', 'cover_status', 'cover_verified', 'cover_comment', 'classic_category')


class AdvancedRecipeSearchForm(forms.Form):
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
    layer = forms.ModelChoiceField(queryset=LayerItem.objects.filter(classic=False).filter(status='P').order_by('name'), empty_label="(any)", required=False)


class RecipeChangesetForm(forms.ModelForm):
    class Meta:
        model = RecipeChangeset
        fields = ('name',)


class BulkChangeEditForm(forms.ModelForm):
    class Meta:
        model = RecipeChange
        fields = ('summary', 'description', 'homepage', 'bugtracker', 'section', 'license')

BulkChangeEditFormSet = modelformset_factory(RecipeChange, form=BulkChangeEditForm, extra=0)


class ClassicRecipeSearchForm(forms.Form):
    COVER_STATUS_CHOICES = [('','(any)'), ('!','(not migrated)')] + ClassicRecipe.COVER_STATUS_CHOICES
    VERIFIED_CHOICES = [
        ('', '(any)'),
        ('1', 'Verified'),
        ('0', 'Unverified'),
        ]

    q = forms.CharField(label='Keyword', max_length=255, required=False)
    category = forms.CharField(max_length=255, required=False)
    cover_status = forms.ChoiceField(label='Status', choices=COVER_STATUS_CHOICES, required=False)
    cover_verified = forms.ChoiceField(label='Verified', choices=VERIFIED_CHOICES, required=False)

