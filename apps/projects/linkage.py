"""
项目统一身份关联工具。

将各模块（API / UI / Midscene / APP）独立项目绑定到公共 projects.Project，
迁移回填与序列化器共用同一套解析/补建逻辑。
"""
from __future__ import annotations


# 模块项目状态 -> 公共项目状态
STATUS_MAP = {
    'NOT_STARTED': 'paused',
    'IN_PROGRESS': 'active',
    'COMPLETED': 'completed',
}


def map_status(module_status):
    """模块项目状态映射为公共项目状态，未知状态默认 active。"""
    return STATUS_MAP.get(module_status or '', 'active')


def find_candidate_main_project(Project, name, owner_id):
    """按 名称+负责人 -> 仅名称 的顺序查找候选公共项目，取最早创建。"""
    queryset = Project.objects.filter(name=name).order_by('created_at', 'id')
    same_owner = queryset.filter(owner_id=owner_id).first()
    if same_owner is not None:
        return same_owner
    return queryset.first()


def is_main_project_occupied(module_model, main_project, exclude_pk=None):
    """判断公共项目是否已被同表其他模块项目占用。"""
    queryset = module_model.objects.filter(main_project_id=main_project.pk)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


def resolve_or_create_main_project(
    Project, module_model, *, name, owner_id, status='', description='', exclude_pk=None
):
    """
    解析模块项目应绑定的公共项目：
    1. 名称+负责人完全匹配则复用；
    2. 仅名称匹配则复用；
    3. 无匹配，或候选已被同表其他项目占用时，自动补建公共项目。
    """
    candidate = find_candidate_main_project(Project, name, owner_id)
    if candidate is not None and not is_main_project_occupied(
        module_model, candidate, exclude_pk=exclude_pk
    ):
        return candidate
    return Project.objects.create(
        name=name,
        description=description or '',
        status=map_status(status),
        owner_id=owner_id,
    )


def backfill_main_projects(Project, module_model):
    """为所有未绑定 main_project 的模块项目回填（幂等，可重复执行）。"""
    count = 0
    for row in module_model.objects.all():
        if getattr(row, 'main_project_id', None) is not None:
            continue
        main_project = resolve_or_create_main_project(
            Project,
            module_model,
            name=row.name,
            owner_id=row.owner_id,
            status=getattr(row, 'status', '') or '',
            description=getattr(row, 'description', '') or '',
            exclude_pk=row.pk,
        )
        row.main_project_id = main_project.pk
        row.save(update_fields=['main_project'])
        count += 1
    return count
