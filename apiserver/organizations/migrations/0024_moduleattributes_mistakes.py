# Generated by Django 4.1.3 on 2023-12-05 12:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0023_moduleattributes_ideal_mistake"),
    ]

    operations = [
        migrations.AddField(
            model_name="moduleattributes",
            name="mistakes",
            field=models.JSONField(default=dict),
        ),
    ]