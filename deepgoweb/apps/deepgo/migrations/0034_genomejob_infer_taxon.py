# Add a per-job toggle for organism-taxon inference (off for archaea/virus demos).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deepgo', '0033_genomejob_timing'),
    ]

    operations = [
        migrations.AddField(
            model_name='genomejob',
            name='infer_taxon',
            field=models.BooleanField(default=True),
        ),
    ]
