from django.db import migrations, models
import django.db.models.deletion


def backfill_main_projects(apps, schema_editor):
    from apps.projects.linkage import backfill_main_projects as run_backfill

    Project = apps.get_model('projects', 'Project')
    AppProject = apps.get_model('app_automation', 'AppProject')
    run_backfill(Project, AppProject)


class Migration(migrations.Migration):

    dependencies = [
        ('app_automation', '0002_initial'),
        ('projects', '0004_project_knowledge_base_updated_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='appproject',
            name='main_project',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='app_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
        migrations.RunPython(backfill_main_projects, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='appproject',
            name='main_project',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='app_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
    ]
