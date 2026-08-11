# Generated manually: 墨刀导入阶段与进度明细字段

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requirement_analysis', '0013_modao_import_async'),
    ]

    operations = [
        migrations.AddField(
            model_name='modaoimport',
            name='stage',
            field=models.CharField(blank=True, default='', max_length=30, verbose_name='当前阶段'),
        ),
        migrations.AddField(
            model_name='modaoimport',
            name='progress_detail',
            field=models.JSONField(blank=True, default=dict, verbose_name='进度明细'),
        ),
    ]
