# Generated by Django 4.1.3 on 2023-05-26 18:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_alter_user_unique_together_alter_user_employee_code"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="employee_code",
        ),
        migrations.RemoveField(
            model_name="user",
            name="grade",
        ),
        migrations.RemoveField(
            model_name="user",
            name="user_filter",
        ),
    ]
