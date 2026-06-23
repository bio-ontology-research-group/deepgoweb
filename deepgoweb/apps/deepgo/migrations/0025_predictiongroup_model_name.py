from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deepgo', '0024_prediction_similar_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictiongroup',
            name='model_name',
            field=models.CharField(
                choices=[
                    ('deepgoplus', 'DeepGOPlus (CNN + DIAMOND)'),
                    ('dgpp-light', 'DeepGO-PlusPlus-Light (DIAMOND + STRING bridge)')],
                default='deepgoplus', max_length=20),
        ),
        migrations.AddField(
            model_name='predictiongroup',
            name='use_cnn',
            field=models.BooleanField(default=False),
        ),
    ]
