# Generated by Django 4.1.3 on 2023-01-31 09:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0005_remove_submodule_max_attempts_and_more"),
        ("accounts", "0005_user_staff"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="user_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("organization admin", "Organization Admin"),
                    ("orgnization learner", "Organization Learner"),
                    ("organization trainer", "Organization Trainer"),
                ],
                help_text="Organization User Type",
                max_length=64,
                null=True,
                verbose_name="User Type",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="employee_code",
            field=models.CharField(blank=True, max_length=100, unique=True),
        ),
    ]
