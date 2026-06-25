# Generated for the DeepGO-PlusPlus-Light result-view contraction option.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deepgo', '0029_predictiongroup_component_predictions'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictiongroup',
            name='contract',
            field=models.BooleanField(default=True),
        ),
    ]
