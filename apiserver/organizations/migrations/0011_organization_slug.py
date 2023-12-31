# Generated by Django 4.1.3 on 2023-03-16 08:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0010_organization_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="slug",
            field=models.SlugField(default="slug", max_length=200),
            preserve_default=False,
        ),
    ]
