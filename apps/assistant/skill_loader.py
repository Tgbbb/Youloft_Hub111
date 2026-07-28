"""
Skill Loader — 扫描本地 skills/ 目录，解析 Skill 定义

Skill 目录结构:
  skills/<skill-name>/
    ├── SKILL.md        (必选) 入口文件，YAML frontmatter + Markdown 正文
    ├── config.yaml      (可选) 元数据覆盖
    └── mcp_config.json  (可选) MCP Server 配置
"""
import os
import re
import json
import time
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# skills/ 目录路径
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'skills')

# Skill 扫描缓存：避免每次请求都读磁盘解析 YAML
# (_cached_skills, _cached_mtimes, _cache_time)
# _cached_mtimes: {filepath: mtime} — 用于检测变更
_skills_cache: Optional[Tuple[List, Dict[str, float], float]] = None
_SKILLS_CACHE_TTL = 60  # 缓存 TTL 秒数，超时后重新检查文件 mtime


@dataclass
class Skill:
    """Skill 数据模型"""
    dir_name: str                        # 目录名
    name: str                            # 唯一标识
    display_name: str = ''               # 显示名称
    description: str = ''                # 简要描述
    instructions: str = ''               # Markdown 正文（指令内容）
    enabled: bool = True                 # 是否启用
    order: int = 0                       # 排序
    yaml_frontmatter: Dict = field(default_factory=dict)  # 完整 YAML
    mcp_config: Optional[Dict] = None    # MCP Server 配置
    has_error: str = ''                  # 解析错误信息


def _parse_frontmatter(content: str) -> tuple:
    """解析 YAML frontmatter + Markdown 正文"""
    fm = {}
    body = content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as e:
                logger.warning(f'Failed to parse frontmatter: {e}')
            body = parts[2].strip()
    return fm, body


def _get_skills_file_mtimes() -> Dict[str, float]:
    """收集所有 Skill 相关文件的 mtime，用于缓存失效检测"""
    mtimes = {}
    if not os.path.isdir(SKILLS_DIR):
        return mtimes
    for entry in os.listdir(SKILLS_DIR):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue
        for fname in ('SKILL.md', 'config.yaml', 'mcp_config.json'):
            fpath = os.path.join(skill_dir, fname)
            if os.path.isfile(fpath):
                try:
                    mtimes[fpath] = os.path.getmtime(fpath)
                except OSError:
                    pass
    return mtimes


def scan_skills(use_cache: bool = True) -> List[Skill]:
    """扫描 skills/ 目录，返回所有 Skill 列表。

    Args:
        use_cache: 是否使用 mtime 缓存（默认 True）。设为 False 强制重新扫描。

    缓存策略：
    - 收集所有 SKILL.md / config.yaml / mcp_config.json 的 mtime
    - 与上次扫描时的 mtime 对比，无变化则直接返回缓存
    - TTL 60s 后主动重新检查（防止新文件被遗漏）
    """
    global _skills_cache

    if not os.path.isdir(SKILLS_DIR):
        os.makedirs(SKILLS_DIR, exist_ok=True)
        return []

    now = time.time()

    if use_cache and _skills_cache is not None:
        cached_skills, cached_mtimes, cache_time = _skills_cache
        # TTL 内直接返回
        if now - cache_time < _SKILLS_CACHE_TTL:
            return cached_skills
        # TTL 过期但 mtime 无变化 → 续期不重扫
        current_mtimes = _get_skills_file_mtimes()
        if current_mtimes == cached_mtimes:
            _skills_cache = (cached_skills, cached_mtimes, now)
            return cached_skills

    # 执行扫描
    skills = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue

        skill_md = os.path.join(skill_dir, 'SKILL.md')
        if not os.path.isfile(skill_md):
            continue

        try:
            with open(skill_md, 'r', encoding='utf-8') as f:
                content = f.read()

            fm, body = _parse_frontmatter(content)

            skill = Skill(
                dir_name=entry,
                name=fm.get('name', entry),
                display_name=fm.get('display_name', entry),
                description=fm.get('description', ''),
                instructions=body,
                enabled=fm.get('enabled', True),
                order=fm.get('order', 0),
                yaml_frontmatter=fm,
            )

            # 检查 config.yaml
            config_yaml = os.path.join(skill_dir, 'config.yaml')
            if os.path.isfile(config_yaml):
                with open(config_yaml, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f) or {}
                    if cfg.get('display_name'):
                        skill.display_name = cfg['display_name']
                    if cfg.get('description'):
                        skill.description = cfg['description']
                    if 'enabled' in cfg:
                        skill.enabled = cfg['enabled']

            # 检查 mcp_config.json
            mcp_json = os.path.join(skill_dir, 'mcp_config.json')
            if os.path.isfile(mcp_json):
                with open(mcp_json, 'r', encoding='utf-8') as f:
                    skill.mcp_config = json.load(f)

            skills.append(skill)

        except Exception as e:
            logger.error(f'Failed to load skill {entry}: {e}')
            skills.append(Skill(
                dir_name=entry,
                name=entry,
                display_name=entry,
                has_error=str(e),
            ))

    # 按 order 排序
    skills.sort(key=lambda s: (s.order, s.dir_name))

    # 更新缓存
    _skills_cache = (skills, _get_skills_file_mtimes(), now)
    logger.debug(f'Skills scanned: {len(skills)} loaded, cache updated')

    return skills


def invalidate_skills_cache():
    """强制失效 Skill 缓存（导入/删除 Skill 后调用）"""
    global _skills_cache
    _skills_cache = None
    logger.debug('Skills cache invalidated')


def get_skill(name: str) -> Optional[Skill]:
    """获取单个 Skill"""
    for skill in scan_skills():
        if skill.name == name:
            return skill
    return None


def get_enabled_skills() -> List[Skill]:
    """获取所有启用的 Skill"""
    return [s for s in scan_skills() if s.enabled and not s.has_error]


def delete_skill(name: str) -> bool:
    """删除一个 Skill 目录"""
    skill_dir = os.path.join(SKILLS_DIR, name)
    if not os.path.isdir(skill_dir):
        # 尝试按 dir_name 查找
        skill = get_skill(name)
        if skill:
            skill_dir = os.path.join(SKILLS_DIR, skill.dir_name)
        else:
            return False

    import shutil
    shutil.rmtree(skill_dir, ignore_errors=True)
    invalidate_skills_cache()
    return not os.path.isdir(skill_dir)


def install_skill(file_path: str) -> Optional[Skill]:
    """
    安装一个 Skill 包（.zip 或目录）
    支持两种格式:
    1. .zip 文件 → 解压到 skills/
    2. 目录 → 复制到 skills/
    """
    import shutil
    import zipfile
    import tempfile

    if file_path.endswith('.zip'):
        # 解压到临时目录
        tmp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.extractall(tmp_dir)

            # 查找 SKILL.md 所在的目录
            for root, dirs, files in os.walk(tmp_dir):
                if 'SKILL.md' in files:
                    skill_name = os.path.basename(root)
                    dest = os.path.join(SKILLS_DIR, skill_name)
                    if os.path.exists(dest):
                        shutil.rmtree(dest)
                    shutil.copytree(root, dest)
                    invalidate_skills_cache()
                    return get_skill(skill_name)

            return None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif os.path.isdir(file_path):
        skill_name = os.path.basename(file_path)
        dest = os.path.join(SKILLS_DIR, skill_name)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(file_path, dest)
        invalidate_skills_cache()
        return get_skill(skill_name)

    return None


def build_skills_prompt() -> str:
    """构建所有启用 Skill 的提示词文本，注入到 Agent system prompt"""
    skills = get_enabled_skills()
    if not skills:
        return ''

    lines = ['\n## 可用技能 (Skills)\n']
    lines.append('用户可以通过 `/skill:name` 格式直接调用技能。收到此格式的消息后，请严格按对应技能的执行流程操作。用户提出相关需求时也请参考技能流程：\n')

    for s in skills:
        lines.append(f'### {s.display_name} (`/skill:{s.name}`)')
        if s.description:
            lines.append(f'说明: {s.description}')
        if s.instructions:
            # 限制长度避免上下文爆炸
            inst = s.instructions[:2000]
            lines.append('执行流程:')
            lines.append(inst)
        if s.mcp_config:
            lines.append('MCP 工具: 已配置（由系统自动加载）')
        lines.append('')

    return '\n'.join(lines)
