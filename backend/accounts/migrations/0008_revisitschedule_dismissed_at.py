from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_add_company_visit_and_revisit_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="revisitschedule",
            name="dismissed_at",
            field=models.DateField(blank=True, null=True),
        ),
    ]
