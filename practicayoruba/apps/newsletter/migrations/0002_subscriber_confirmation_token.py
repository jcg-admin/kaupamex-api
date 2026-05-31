import apps.newsletter.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newsletter', '0001_squashed_0002_newslettersubscriber_softdelete'),
    ]

    operations = [
        migrations.AddField(
            model_name='newslettersubscriber',
            name='confirmation_token',
            field=models.CharField(blank=True, default=None, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='newslettersubscriber',
            name='unsubscribe_token',
            field=models.CharField(
                default=apps.newsletter.models._generate_unsubscribe_token,
                max_length=200,
                unique=True,
            ),
        ),
    ]
