from django.db import migrations, models
import django.db.models.deletion


def backfill_main_projects(apps, schema_editor):
    from apps.projects.linkage import backfill_main_projects as run_backfill

    Project = apps.get_model('projects', 'Project')
    ApiProject = apps.get_model('api_testing', 'ApiProject')
    run_backfill(Project, ApiProject)


class Migration(migrations.Migration):

    dependencies = [
        ('api_testing', '0003_environment_base_url_environment_default_headers_and_more'),
        ('projects', '0004_project_knowledge_base_updated_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='apiproject',
            name='main_project',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='api_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
        migrations.RunPython(backfill_main_projects, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='apiproject',
            name='main_project',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='api_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
    ]
