# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def set_commit_url(apps, schema_editor):
    import re
    LayerItem = apps.get_model('layerindex', 'LayerItem')
    for layer in LayerItem.objects.all():
        if layer.vcs_web_url:
            if 'git.yoctoproject.org' in layer.vcs_web_url or 'git.openembedded.org' in layer.vcs_web_url or 'cgit.' in layer.vcs_web_url:
                layer.vcs_web_commit_url = layer.vcs_web_url + '/commit/?id=%hash%'
            elif 'github.com/' in layer.vcs_web_url:
                layer.vcs_web_commit_url = layer.vcs_web_url + '/commit/%hash%'
            elif 'bitbucket.org/' in layer.vcs_web_url:
                layer.vcs_web_commit_url = layer.vcs_web_url + '/commits/%hash%'
            elif 'gitlab.' in layer.vcs_web_url:
                layer.vcs_web_commit_url = layer.vcs_web_url + '/commit/%hash%'
            elif 'a=tree;' in layer.vcs_web_tree_base_url:
                layer.vcs_web_commit_url = re.sub(r'\.git.*', '.git;a=commit;h=%hash%', layer.vcs_web_url)
            layer.save()

class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0011_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='layeritem',
            name='vcs_web_commit_url',
            field=models.CharField(verbose_name='Repository web interface commit URL', max_length=255, blank=True, help_text='Base URL for the web interface for viewing a single commit within the repository, if any'),
        ),
        migrations.RunPython(set_commit_url, reverse_code=migrations.RunPython.noop),
    ]
