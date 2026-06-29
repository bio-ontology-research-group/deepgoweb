from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('deepgo', '0034_genomejob_infer_taxon'),
    ]

    operations = [
        migrations.AddField(
            model_name='release',
            name='predictor_type',
            field=models.CharField(
                choices=[('deepgoplus', 'DeepGOPlus'),
                         ('dgpp-light', 'DeepGO-PlusPlus-Light')],
                default='deepgoplus', max_length=20),
        ),
        migrations.AlterField(
            model_name='release',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='release',
            name='data_root',
            field=models.FilePathField(
                allow_files=False, allow_folders=True, max_length=512,
                path='/opt-data/extracted/'),
        ),
        migrations.CreateModel(
            name='CafaMetrics',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('knowledge_class', models.CharField(
                    choices=[('no_knowledge', 'No-knowledge (novel proteins)'),
                             ('limited', 'Limited-knowledge'),
                             ('partial', 'Partial-knowledge'),
                             ('overall', 'Overall')],
                    default='no_knowledge', max_length=20)),
                ('fmax', models.FloatField(
                    help_text='IA-weighted F-max (CAFA official metric)')),
                ('fmax_mf', models.FloatField(blank=True, null=True)),
                ('fmax_bp', models.FloatField(blank=True, null=True)),
                ('fmax_cc', models.FloatField(blank=True, null=True)),
                ('coverage', models.FloatField(blank=True, null=True)),
                ('protocol', models.CharField(default='cafa6-recon', max_length=64)),
                ('notes', models.TextField(blank=True, default='')),
                ('computed_date', models.DateTimeField(
                    default=django.utils.timezone.now)),
                ('release', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cafa_metrics', to='deepgo.release')),
            ],
            options={
                'verbose_name_plural': 'CAFA metrics',
                'unique_together': {('release', 'knowledge_class', 'protocol')},
            },
        ),
    ]
