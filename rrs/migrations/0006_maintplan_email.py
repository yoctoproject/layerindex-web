# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rrs', '0005_release_plan_nonnull'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceplan',
            name='admin',
            field=models.ForeignKey(blank=True, null=True, help_text='Plan administrator', to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='maintenanceplan',
            name='email_enabled',
            field=models.BooleanField(verbose_name='Enable emails', default=False, help_text='Enable automatically sending report emails for this plan'),
        ),
        migrations.AddField(
            model_name='maintenanceplan',
            name='email_from',
            field=models.CharField(max_length=255, blank=True, help_text='Sender for automated emails'),
        ),
        migrations.AddField(
            model_name='maintenanceplan',
            name='email_subject',
            field=models.CharField(max_length=255, blank=True, default='[Recipe reporting system] Upgradable recipe name list', help_text='Subject line of automated emails'),
        ),
        migrations.AddField(
            model_name='maintenanceplan',
            name='email_to',
            field=models.CharField(max_length=255, blank=True, help_text='Recipient for automated emails (separate multiple addresses with ;)'),
        ),
    ]
