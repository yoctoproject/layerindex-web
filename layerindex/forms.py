# layerindex-web - form definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import LayerItem
from django import forms
from django.core.validators import URLValidator, RegexValidator, email_re
import re

class SubmitLayerForm(forms.ModelForm):
    # Additional form fields
    maintainers = forms.CharField(max_length=200)
    deps = forms.ModelMultipleChoiceField(label='Other layers this layer depends upon', queryset=LayerItem.objects.all(), required=False)

    class Meta:
        model = LayerItem
        fields = ('name', 'layer_type', 'summary', 'description', 'vcs_url', 'vcs_subdir', 'vcs_web_url', 'vcs_web_tree_base_url', 'vcs_web_file_base_url', 'usage_url')

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

    def clean_maintainers(self):
        maintainers = self.cleaned_data['maintainers'].strip()
        addrs = re.split(r'"?([^"@$<>]+)"? *<([^<> ]+)>,? *', maintainers)
        addrs = [addr.strip() for addr in addrs if addr]
        if addrs and len(addrs) % 2 == 0:
            addrdict = {}
            reg = re.compile(email_re)
            for i in range(0, len(addrs)-1,2):
                email = addrs[i+1]
                if not reg.match(email):
                    raise forms.ValidationError('%s is not a valid email address' % email)
                addrdict[addrs[i]] = email
            maintainers = addrdict
        else:
            raise forms.ValidationError('Please enter one or more maintainers in email address format (i.e. "Full Name <emailaddress@example.com> separated by commas")')

        return maintainers
