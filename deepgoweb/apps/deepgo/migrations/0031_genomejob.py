# Generated for the DeepGO-GSPA genome-scale annotation tab (GenomeJob model).

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('deepgo', '0030_predictiongroup_contract'),
    ]

    operations = [
        migrations.CreateModel(
            name='GenomeJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(
                    choices=[('pending', 'Queued'), ('running', 'Running'),
                             ('done', 'Completed'), ('error', 'Failed')],
                    default='pending', max_length=10)),
                ('genome_filename', models.CharField(blank=True, default='', max_length=255)),
                ('genome_data', models.TextField(blank=True, default='')),
                ('gff3_filename', models.CharField(blank=True, default='', max_length=255)),
                ('gff3_data', models.TextField(blank=True, default='')),
                ('proteins_filename', models.CharField(blank=True, default='', max_length=255)),
                ('proteins_data', models.TextField(blank=True, default='')),
                ('predictor', models.CharField(
                    choices=[('light', 'DeepGO-PlusPlus-Light (CPU, self-contained)'),
                             ('full', 'DeepGO-PlusPlus (full)'),
                             ('none', 'No prediction (metrics only)')],
                    default='light', max_length=10)),
                ('metrics_scope', models.CharField(
                    choices=[('contig', 'Per contig (recommended)'),
                             ('genome', 'Whole genome (pooled)'), ('both', 'Both')],
                    default='contig', max_length=10)),
                ('kingdom', models.CharField(blank=True, default='', max_length=20)),
                ('mag', models.BooleanField(default=False)),
                ('enforce_consistency', models.BooleanField(default=False)),
                ('consistency_mode', models.CharField(
                    choices=[('remove', 'Remove inconsistent terms'),
                             ('downrank', 'Down-rank inconsistent terms'),
                             ('flag', 'Flag only'),
                             ('minimal-flip', 'Minimal-flip (joint MaxSAT)')],
                    default='remove', max_length=15)),
                ('taxon', models.CharField(blank=True, default='', max_length=40)),
                ('enforce_completeness', models.BooleanField(default=False)),
                ('enforce_coherence', models.BooleanField(default=False)),
                ('provenance', models.BooleanField(default=True)),
                ('per_contig_metrics', models.JSONField(blank=True, null=True)),
                ('annotations', models.JSONField(blank=True, null=True)),
                ('enforcement_actions', models.JSONField(blank=True, null=True)),
                ('log', models.TextField(blank=True, default='')),
                ('error', models.TextField(blank=True, default='')),
                ('user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='genome_jobs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
