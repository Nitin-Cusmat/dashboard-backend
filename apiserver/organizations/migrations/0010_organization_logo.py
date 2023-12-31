# Generated by Django 4.1.3 on 2023-03-15 10:07

from django.db import migrations, models
import organizations.models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0009_remove_moduleactivity_last_accessed_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="logo",
            field=models.ImageField(
                blank=True, upload_to=organizations.models.logo_path
            ),
        ),
    ]
