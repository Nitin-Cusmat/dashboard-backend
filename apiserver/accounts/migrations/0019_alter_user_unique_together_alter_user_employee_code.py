# Generated by Django 4.1.3 on 2023-05-18 14:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0018_alter_attempt_unique_together"),
        ("accounts", "0018_alter_user_unique_together"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="user",
            unique_together={("organization", "user_id")},
        ),
        migrations.AlterField(
            model_name="user",
            name="employee_code",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
