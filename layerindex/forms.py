# layerindex-web - form definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import LayerItem, LayerMaintainer
from django import forms
from django.core.validators import URLValidator, RegexValidator, email_re
from django.forms.models import inlineformset_factory
import re


class LayerMaintainerForm(forms.ModelForm):
    class Meta:
        model = LayerMaintainer
        fields = ('name', 'email', 'responsibility')

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email:
            if len(email) < 7:
                raise forms.ValidationError('%s is not a valid email address' % email)
            reg = re.compile(email_re)
            if not reg.match(email):
                raise forms.ValidationError('%s is not a valid email address' % email)

        return email

class BaseLayerMaintainerFormSet(forms.models.BaseInlineFormSet):
    def _construct_form(self, i, **kwargs):
        f = super(BaseLayerMaintainerFormSet, self)._construct_form(i, **kwargs)
        # Ensure the first form in the formset gets filled in
        if i == 0:
            f.empty_permitted = False
            f.required = True
        return f

LayerMaintainerFormSet = inlineformset_factory(LayerItem, LayerMaintainer, form=LayerMaintainerForm, formset=BaseLayerMaintainerFormSet,  can_delete=False)

class SubmitLayerForm(forms.ModelForm):
    # Additional form fields
    deps = forms.ModelMultipleChoiceField(label='Other layers this layer depends upon', queryset=LayerItem.objects.all(), required=False)

    class Meta:
        model = LayerItem
        fields = ('name', 'layer_type', 'summary', 'description', 'vcs_url', 'vcs_subdir', 'vcs_web_url', 'vcs_web_tree_base_url', 'vcs_web_file_base_url', 'usage_url', 'mailing_list_url')

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['deps'].initial = [d.dependency.pk for d in self.instance.dependencies_set.all()]
        else:
            self.fields['deps'].initial = [l.pk for l in LayerItem.objects.filter(name='openembedded-core')]
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
            val = URLValidator(verify_exists=False)
            val(url)
        return url

    def clean_vcs_web_file_base_url(self):
        url = self.cleaned_data['vcs_web_file_base_url'].strip()
        if url:
            val = URLValidator(verify_exists=False)
            val(url)
        return url
