# Add per-phase wall-clock timing to GenomeJob.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deepgo', '0032_genomejob_taxon_inference'),
    ]

    operations = [
        migrations.AddField(
            model_name='genomejob',
            name='timing',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
