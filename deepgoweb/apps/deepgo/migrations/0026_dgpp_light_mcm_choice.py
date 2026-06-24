from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the 'dgpp-light-mcm' (hierarchy-aware CNN) model choice. Choices are not
    enforced at the DB level, so this AlterField is a no-op on the schema; it keeps
    the migration state in sync with the model (makemigrations --check)."""

    dependencies = [
        ('deepgo', '0025_predictiongroup_model_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='predictiongroup',
            name='model_name',
            field=models.CharField(
                choices=[
                    ('deepgoplus', 'DeepGOPlus (CNN + DIAMOND)'),
                    ('dgpp-light', 'DeepGO-PlusPlus-Light (DIAMOND + STRING bridge)'),
                    ('dgpp-light-mcm', 'DeepGO-PlusPlus-Light, hierarchy-aware CNN (CPU)')],
                default='deepgoplus', max_length=20),
        ),
    ]
