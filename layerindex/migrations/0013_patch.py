# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0012_layeritem_vcs_commit_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='Patch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('path', models.CharField(max_length=255)),
                ('src_path', models.CharField(max_length=255)),
                ('status', models.CharField(default='U', choices=[('U', 'Unknown'), ('A', 'Accepted'), ('P', 'Pending'), ('I', 'Inappropriate'), ('B', 'Backport'), ('S', 'Submitted'), ('D', 'Denied')], max_length=1)),
                ('status_extra', models.CharField(blank=True, max_length=255)),
                ('recipe', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.Recipe')),
            ],
            options={
                'verbose_name_plural': 'Patches',
            },
        ),
    ]
