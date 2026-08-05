"""API测试工具函数（兼容层）

执行逻辑已统一迁移到 services.py，这里保留旧函数签名以兼容
views.py 和定时任务等历史调用。
"""
from .services import (
    execute_assertions,
    execute_single_request as execute_api_request,
    execute_suite as execute_test_suite,
)

__all__ = ['execute_assertions', 'execute_api_request', 'execute_test_suite']
