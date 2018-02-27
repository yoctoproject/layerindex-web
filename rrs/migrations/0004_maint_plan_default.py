# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import settings


def populate_plan(apps, schema_editor):
    Release = apps.get_model('rrs', 'Release')
    MaintenancePlan = apps.get_model('rrs', 'MaintenancePlan')
    LayerBranch = apps.get_model('layerindex', 'LayerBranch')
    MaintenancePlanLayerBranch = apps.get_model('rrs', 'MaintenancePlanLayerBranch')

    if Release.objects.all().exists():
        if not settings.CORE_LAYER_NAME:
            raise Exception('Please set CORE_LAYER_NAME in settings.py')
        core_layerbranch = LayerBranch.objects.filter(layer__name=settings.CORE_LAYER_NAME).first()
        if not core_layerbranch:
            raise Exception('Unable to find core layer "%s" specified in CORE_LAYER_NAME in settings.py - please set up the layerindex application first' % settings.CORE_LAYER_NAME)
        maintplan = MaintenancePlan()
        maintplan.name = 'Default'
        maintplan.description = 'Created upon database upgrade'
        maintplan.save()
        for row in Release.objects.all():
            row.plan = maintplan
            row.save()
        maintplanlayerbranch = MaintenancePlanLayerBranch(plan=maintplan, layerbranch=core_layerbranch)
        maintplanlayerbranch.save();


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0003_release_plan'),
    ]

    operations = [
        migrations.RunPython(populate_plan, reverse_code=migrations.RunPython.noop),
    ]
