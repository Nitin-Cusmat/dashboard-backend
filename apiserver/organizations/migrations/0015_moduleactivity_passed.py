# Generated by Django 4.1.3 on 2023-04-04 07:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "organizations",
            "0014_alter_category_options_alter_levelactivity_options_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="moduleactivity",
            name="passed",
            field=models.BooleanField(default=False),
        ),
    ]
