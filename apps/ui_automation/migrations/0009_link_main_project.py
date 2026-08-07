from django.db import migrations, models
import django.db.models.deletion


def backfill_main_projects(apps, schema_editor):
    from apps.projects.linkage import backfill_main_projects as run_backfill

    Project = apps.get_model('projects', 'Project')
    UiProject = apps.get_model('ui_automation', 'UiProject')
    MidsceneProject = apps.get_model('ui_automation', 'MidsceneProject')
    run_backfill(Project, UiProject)
    run_backfill(Project, MidsceneProject)


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0008_add_replay_data_to_midscene_case'),
        ('projects', '0004_project_knowledge_base_updated_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='uiproject',
            name='main_project',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ui_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
        migrations.AddField(
            model_name='midsceneproject',
            name='main_project',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='midscene_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
        migrations.RunPython(backfill_main_projects, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='uiproject',
            name='main_project',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ui_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
        migrations.AlterField(
            model_name='midsceneproject',
            name='main_project',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='midscene_project',
                to='projects.project',
                verbose_name='主项目',
            ),
        ),
    ]
