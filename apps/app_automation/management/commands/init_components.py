"""
初始化 APP 自动化测试的基础组件库
用法: python manage.py init_components
"""
from django.core.management.base import BaseCommand
from apps.app_automation.models import AppComponent


def _selector_schema():
    """生成定位相关的通用 schema 字段"""
    return {
        'target_selector_type': {
            'type': 'string', 'enum': ['image', 'pos', 'region'],
            'default': 'image',
            'description': '目标定位方式'
        },
        'target_selector': {
            'type': 'string',
            'description': '目标定位值（image: 文件名, pos: x,y, region: x1,y1,x2,y2）'
        },
        'image_scope': {
            'type': 'string', 'default': 'common',
            'description': '图片查找目录（Template/ 下的子目录名）'
        },
        'image_threshold': {
            'type': 'number', 'default': 0.8,
            'description': '图片匹配阈值(0.7~1.0)'
        },
    }


def _swipe_selector_schema():
    """滑动操作需要的起止定位"""
    s = {}
    s['start_selector_type'] = {'type': 'string', 'enum': ['pos'], 'default': 'pos', 'description': '起点定位方式'}
    s['start_selector'] = {'type': 'string', 'description': '起点坐标(pos: x,y)'}
    s['end_selector_type'] = {'type': 'string', 'enum': ['pos'], 'default': 'pos', 'description': '终点定位方式'}
    s['end_selector'] = {'type': 'string', 'description': '终点坐标(pos: x,y)'}
    s['duration'] = {'type': 'number', 'default': 0.3, 'description': '滑动持续时间(秒)'}
    return s


DEFAULT_COMPONENTS = [
    # ========== 基础操作类 ==========
    {
        'name': '点击',
        'type': 'tap',
        'category': '基础操作',
        'description': '点击屏幕指定元素或坐标',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'times': {'type': 'integer', 'default': 1, 'description': '点击次数'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'times': 1, 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 1,
    },
    {
        'name': '滑动',
        'type': 'swipe',
        'category': '基础操作',
        'description': '从一点滑动到另一点',
        'schema': {
            'type': 'object',
            'properties': {
                **_swipe_selector_schema(),
            }
        },
        'default_config': {'start_selector_type': 'pos', 'end_selector_type': 'pos', 'duration': 0.3},
        'sort_order': 2,
    },
    {
        'name': '文本输入',
        'type': 'text',
        'category': '基础操作',
        'description': '在输入框中输入文本',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'value': {'type': 'string', 'description': '要输入的文本内容'},
                'send_enter': {'type': 'boolean', 'default': False, 'description': '输入后是否发送回车'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'send_enter': False, 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 3,
    },
    {
        'name': '等待',
        'type': 'sleep',
        'category': '基础操作',
        'description': '等待指定时间',
        'schema': {
            'type': 'object',
            'properties': {
                'seconds': {'type': 'number', 'default': 1, 'description': '等待时间(秒)'},
            }
        },
        'default_config': {'seconds': 1},
        'sort_order': 4,
    },
    {
        'name': '截图',
        'type': 'snapshot',
        'category': '基础操作',
        'description': '截取当前屏幕（执行记录中可查看）',
        'schema': {
            'type': 'object',
            'properties': {
                'note': {'type': 'string', 'description': '截图备注(可选)'},
            }
        },
        'default_config': {},
        'sort_order': 5,
    },

    # ========== 断言检查类 ==========
    {
        'name': '断言存在',
        'type': 'assert_exists',
        'category': '断言检查',
        'description': '验证指定元素存在于屏幕上',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'timeout': {'type': 'number', 'default': 5, 'description': '超时时间(秒)'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'timeout': 5, 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 10,
    },
    {
        'name': '断言不存在',
        'type': 'assert_not_exists',
        'category': '断言检查',
        'description': '验证指定元素不存在于屏幕上',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'timeout': {'type': 'number', 'default': 5, 'description': '超时时间(秒)'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'timeout': 5, 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 11,
    },
    {
        'name': '断言文本',
        'type': 'assert_text',
        'category': '断言检查',
        'description': '验证屏幕上存在指定文本内容',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'expected': {'type': 'string', 'description': '期望出现的文本'},
                'match_mode': {'type': 'string', 'enum': ['contains', 'exact'], 'default': 'contains', 'description': '匹配模式'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'match_mode': 'contains', 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 12,
    },

    # ========== 系统操作类 ==========
    {
        'name': '返回',
        'type': 'keyevent_back',
        'category': '系统操作',
        'description': '按返回键',
        'schema': {'type': 'object', 'properties': {}},
        'default_config': {},
        'sort_order': 20,
    },
    {
        'name': 'Home键',
        'type': 'keyevent_home',
        'category': '系统操作',
        'description': '按Home键回到桌面',
        'schema': {'type': 'object', 'properties': {}},
        'default_config': {},
        'sort_order': 21,
    },
    {
        'name': '启动应用',
        'type': 'start_app',
        'category': '系统操作',
        'description': '启动指定的APP',
        'schema': {
            'type': 'object',
            'properties': {
                'package': {'type': 'string', 'description': 'APP包名'},
            }
        },
        'default_config': {},
        'sort_order': 22,
    },
    {
        'name': '停止应用',
        'type': 'stop_app',
        'category': '系统操作',
        'description': '停止指定的APP',
        'schema': {
            'type': 'object',
            'properties': {
                'package': {'type': 'string', 'description': 'APP包名'},
            }
        },
        'default_config': {},
        'sort_order': 23,
    },
    {
        'name': '清除文本',
        'type': 'clear_text',
        'category': '系统操作',
        'description': '清除输入框中的文本',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
            }
        },
        'default_config': {'target_selector_type': 'image', 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 24,
    },

    # ========== 高级操作类 ==========
    {
        'name': '双击',
        'type': 'double_tap',
        'category': '高级操作',
        'description': '双击指定位置',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
            }
        },
        'default_config': {'target_selector_type': 'pos', 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 30,
    },
    {
        'name': '长按',
        'type': 'long_press',
        'category': '高级操作',
        'description': '长按指定位置',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'duration': {'type': 'number', 'default': 1.0, 'description': '长按时间(秒)'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'duration': 1.0, 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 31,
    },

    # ========== 控制流类 ==========
    {
        'name': '条件分支 (If/Else)',
        'type': 'if',
        'category': '控制流',
        'description': '根据条件判断执行不同分支。支持 ==, !=, >, <, in, contains, regex 等操作符',
        'schema': {
            'type': 'object',
            'properties': {
                'left': {'type': 'string', 'description': '左值（变量名用 {{variable}} 引用）'},
                'operator': {'type': 'string', 'enum': ['==', '!=', '>', '>=', '<', '<=', 'in', 'not_in', 'contains', 'not_contains', 'regex', 'truthy', 'falsy', 'startswith', 'endswith'], 'default': '==', 'description': '比较操作符'},
                'right': {'type': 'string', 'description': '右值（字面量或变量）'},
            }
        },
        'default_config': {'operator': '==', 'left': '', 'right': ''},
        'sort_order': 40,
    },
    {
        'name': '循环 (Loop)',
        'type': 'loop',
        'category': '控制流',
        'description': '重复执行子步骤。支持计数循环和条件循环',
        'schema': {
            'type': 'object',
            'properties': {
                'mode': {'type': 'string', 'enum': ['count', 'condition'], 'default': 'count', 'description': '循环模式'},
                'max_loops': {'type': 'integer', 'default': 10, 'description': '最大循环次数'},
                'interval': {'type': 'number', 'default': 0, 'description': '每次循环间隔(秒)'},
                'left': {'type': 'string', 'description': '条件循环的左值'},
                'operator': {'type': 'string', 'enum': ['==', '!=', '>', '<', 'in', 'contains'], 'default': '==', 'description': '条件操作符'},
                'right': {'type': 'string', 'description': '条件循环的右值'},
            }
        },
        'default_config': {'mode': 'count', 'max_loops': 10, 'interval': 0},
        'sort_order': 41,
    },
    {
        'name': '顺序执行',
        'type': 'sequence',
        'category': '控制流',
        'description': '顺序执行一组子步骤',
        'schema': {'type': 'object', 'properties': {}},
        'default_config': {},
        'sort_order': 42,
    },
    {
        'name': '异常捕获 (Try/Catch)',
        'type': 'try',
        'category': '控制流',
        'description': '尝试执行子步骤，失败时执行捕获分支',
        'schema': {'type': 'object', 'properties': {}},
        'default_config': {},
        'sort_order': 43,
    },

    # ========== 变量操作类 ==========
    {
        'name': '设置变量',
        'type': 'set_variable',
        'category': '变量操作',
        'description': '设置一个变量值（支持 local/global/outputs 作用域）',
        'schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': '变量名'},
                'value': {'type': 'string', 'description': '变量值（支持 {{variable}} 引用）'},
                'scope': {'type': 'string', 'enum': ['local', 'global', 'outputs'], 'default': 'local', 'description': '作用域'},
                'value_type': {'type': 'string', 'enum': ['string', 'number', 'boolean', 'array', 'object'], 'default': 'string', 'description': '值类型'},
            }
        },
        'default_config': {'scope': 'local', 'value_type': 'string'},
        'sort_order': 50,
    },
    {
        'name': '清除变量',
        'type': 'unset_variable',
        'category': '变量操作',
        'description': '清除一个变量',
        'schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': '变量名'},
            }
        },
        'default_config': {},
        'sort_order': 51,
    },
    {
        'name': '提取输出',
        'type': 'extract_output',
        'category': '变量操作',
        'description': '从步骤结果中提取值并存储为变量',
        'schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': '变量名'},
                'source': {'type': 'string', 'description': '提取源'},
            }
        },
        'default_config': {},
        'sort_order': 52,
    },

    # ========== 网络类 ==========
    {
        'name': 'API 请求',
        'type': 'api_request',
        'category': '网络',
        'description': '发送 HTTP API 请求',
        'schema': {
            'type': 'object',
            'properties': {
                'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], 'default': 'GET', 'description': 'HTTP 方法'},
                'url': {'type': 'string', 'description': '请求 URL'},
                'headers': {'type': 'string', 'description': '请求头（JSON 格式）'},
                'body': {'type': 'string', 'description': '请求体'},
            }
        },
        'default_config': {'method': 'GET'},
        'sort_order': 60,
    },

    # ========== 高级交互类 ==========
    {
        'name': '图片存在则点击',
        'type': 'image_exists_click',
        'category': '高级交互',
        'description': '检查图片是否存在，存在则点击，不存在则跳过',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
            }
        },
        'default_config': {'target_selector_type': 'image', 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 70,
    },
    {
        'name': '链式图片点击',
        'type': 'image_exists_click_chain',
        'category': '高级交互',
        'description': '依次检查多张图片，点击第一张存在的',
        'schema': {
            'type': 'object',
            'properties': {
                'targets': {'type': 'string', 'description': '目标列表（JSON 格式）'},
            }
        },
        'default_config': {},
        'sort_order': 71,
    },
    {
        'name': '拖拽',
        'type': 'drag',
        'category': '高级交互',
        'description': '从起点拖拽到终点',
        'schema': {
            'type': 'object',
            'properties': {
                'start_selector_type': {'type': 'string', 'enum': ['image', 'pos'], 'default': 'pos', 'description': '起点定位方式'},
                'start_selector': {'type': 'string', 'description': '起点（image: 文件名, pos: x,y）'},
                'end_selector_type': {'type': 'string', 'enum': ['image', 'pos'], 'default': 'pos', 'description': '终点定位方式'},
                'end_selector': {'type': 'string', 'description': '终点（image: 文件名, pos: x,y）'},
                'duration': {'type': 'number', 'default': 0.5, 'description': '拖拽持续时间(秒)'},
            }
        },
        'default_config': {'start_selector_type': 'pos', 'end_selector_type': 'pos', 'duration': 0.5},
        'sort_order': 72,
    },
    {
        'name': '滑动直到找到',
        'type': 'swipe_to',
        'category': '高级交互',
        'description': '反复滑动直到目标元素出现',
        'schema': {
            'type': 'object',
            'properties': {
                **_selector_schema(),
                'direction': {'type': 'string', 'enum': ['up', 'down', 'left', 'right'], 'default': 'up', 'description': '滑动方向'},
                'max_swipes': {'type': 'integer', 'default': 5, 'description': '最大滑动次数'},
                'interval': {'type': 'number', 'default': 0.5, 'description': '每次滑动间隔(秒)'},
            }
        },
        'default_config': {'target_selector_type': 'image', 'direction': 'up', 'max_swipes': 5, 'interval': 0.5, 'image_scope': 'common', 'image_threshold': 0.8},
        'sort_order': 73,
    },
    {
        'name': '遍历断言',
        'type': 'foreach_assert',
        'category': '高级交互',
        'description': '遍历列表，对每个元素执行断言',
        'schema': {
            'type': 'object',
            'properties': {
                'expected_list': {'type': 'string', 'description': '期望值列表（逗号分隔或多行）'},
                'max_loops': {'type': 'integer', 'default': 5, 'description': '最大循环次数'},
                'timeout': {'type': 'number', 'default': 5, 'description': '超时时间(秒)'},
                'match_mode': {'type': 'string', 'enum': ['contains', 'exact'], 'default': 'contains', 'description': '匹配模式'},
            }
        },
        'default_config': {'max_loops': 5, 'timeout': 5, 'match_mode': 'contains'},
        'sort_order': 74,
    },
]


class Command(BaseCommand):
    help = '初始化 APP 自动化测试组件库（含正确的 schema 字段）'

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for comp_data in DEFAULT_COMPONENTS:
            obj, is_new = AppComponent.objects.update_or_create(
                type=comp_data['type'],
                defaults=comp_data
            )
            if is_new:
                created += 1
            else:
                updated += 1
            self.stdout.write(f'  {"+" if is_new else "~"} {obj.name} ({obj.type})')

        self.stdout.write(self.style.SUCCESS(
            f'\nComponent library initialized: {created} created, {updated} updated'
        ))
