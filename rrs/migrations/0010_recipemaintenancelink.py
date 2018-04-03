# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def insert_initial_link_data(apps, schema_editor):
    RecipeMaintenanceLink = apps.get_model('rrs', 'RecipeMaintenanceLink')

    r = RecipeMaintenanceLink(pn_match='gcc-cross-*', pn_target='gcc')
    r.save()
    r = RecipeMaintenanceLink(pn_match='gcc-crosssdk-*', pn_target='gcc')
    r.save()
    r = RecipeMaintenanceLink(pn_match='gcc-source-*', pn_target='gcc')
    r.save()
    r = RecipeMaintenanceLink(pn_match='binutils-cross-*', pn_target='binutils')
    r.save()
    r = RecipeMaintenanceLink(pn_match='binutils-crosssdk-*', pn_target='binutils')
    r.save()
    r = RecipeMaintenanceLink(pn_match='gdb-cross-*', pn_target='gdb')
    r.save()


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0009_rmh_layerbranch'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecipeMaintenanceLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('pn_match', models.CharField(max_length=100, help_text='Expression to match against pn of recipes that should be linked (glob expression)')),
                ('pn_target', models.CharField(max_length=100, help_text='Name of recipe to link to')),
            ],
        ),
        migrations.RunPython(insert_initial_link_data, reverse_code=migrations.RunPython.noop),
    ]
