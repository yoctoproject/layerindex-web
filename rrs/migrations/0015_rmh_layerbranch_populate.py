# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import settings


def populate_rmh_layerbranch(apps, schema_editor):
    RecipeMaintainerHistory = apps.get_model('rrs', 'RecipeMaintainerHistory')
    LayerBranch = apps.get_model('layerindex', 'LayerBranch')
    if not settings.CORE_LAYER_NAME:
        raise Exception('Please set CORE_LAYER_NAME in settings.py')
    core_layerbranch = LayerBranch.objects.filter(layer__name=settings.CORE_LAYER_NAME).first()
    if not core_layerbranch:
        raise Exception('Unable to find core layer "%s" specified in CORE_LAYER_NAME in settings.py - please set up the layerindex application first' % settings.CORE_LAYER_NAME)
    for row in RecipeMaintainerHistory.objects.all():
        row.layerbranch = core_layerbranch
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0014_reup_layerbranch_nonnull'),
    ]

    operations = [
        migrations.RunPython(populate_rmh_layerbranch, reverse_code=migrations.RunPython.noop),
    ]
