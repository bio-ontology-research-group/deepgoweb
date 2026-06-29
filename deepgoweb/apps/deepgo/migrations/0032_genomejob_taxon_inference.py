# Add inferred-taxon result fields to GenomeJob (Asaad-style taxon inference).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deepgo', '0031_genomejob'),
    ]

    operations = [
        migrations.AddField(
            model_name='genomejob',
            name='inferred_taxon',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='genomejob',
            name='taxon_inference',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
