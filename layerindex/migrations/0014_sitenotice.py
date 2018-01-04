# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0013_patch'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteNotice',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('text', models.TextField(help_text='Text to show in the notice. A limited subset of HTML is supported for formatting.')),
                ('level', models.CharField(choices=[('I', 'Info'), ('S', 'Success'), ('W', 'Warning'), ('E', 'Error')], help_text='Level of notice to display', default='I', max_length=1)),
                ('disabled', models.BooleanField(verbose_name='Disabled', help_text='Use to temporarily disable this notice', default=False)),
                ('expires', models.DateTimeField(blank=True, help_text='Optional date/time when this notice will stop showing', null=True)),
            ],
        ),
    ]
