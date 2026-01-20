from django.db import migrations, models, transaction

from wizard.constants import IN_PROGRESS_CHOICE, MAP_WIZARD_SECTION, PROJECT_CHOICE


def remove_wizard_sections(apps, schema_editor):
    WizardSection = apps.get_model('wizard', 'WizardSection')
    WizardSection.objects.all().delete()


def create_wizard_sections(apps, schema_editor):
    WizardSection = apps.get_model('wizard', 'WizardSection')
    objects_to_create = [WizardSection(id=1, step=1, name=PROJECT_CHOICE, status=IN_PROGRESS_CHOICE)]

    for index, name in enumerate(list(MAP_WIZARD_SECTION.keys())[1:]):
        index += 2
        objects_to_create.append(WizardSection(id=index, step=index, name=name))

    WizardSection.objects.bulk_create(objects_to_create)


class Migration(migrations.Migration):
    dependencies = [
        ("wizard", "0008_alter_wizardsection_options_wizardsection_step"),
    ]

    operations = [
        migrations.RunPython(transaction.atomic(remove_wizard_sections)),
        migrations.AlterField(
            model_name="wizardsection",
            name="name",
            field=models.SlugField(
                choices=[
                    ("project", "Project Description"),
                    (
                        "administrative_levels",
                        "Administrative Level Structure Configuration",
                    ),
                    ("administrative_regions", "Load Administrative Levels"),
                    ("departments", "Departments"),
                    ("issue_types", "Types"),
                    ("categories", "Issues Categories"),
                    ("issue_status", "Resolution Process"),
                    ("citizen_age_groups", "Citizen Age Groups"),
                    ("citizen_groups", "Citizen Groups"),
                    ("components", "Sub Component"),
                ],
                max_length=255,
                unique=True,
            ),
        ),
        migrations.RunPython(transaction.atomic(create_wizard_sections)),
    ]
