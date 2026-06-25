from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0051_fix_yoctoproject_cgit_urls'),
    ]

    operations = [
        migrations.AddField(
            model_name='source',
            name='path',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
