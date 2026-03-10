"""
Overleaf 自定义异常类
"""


class OverleafAuthError(Exception):
    """Cookie 失效或无权限访问项目。"""


class OverleafNotFoundError(Exception):
    """项目或资源不存在。"""


class OverleafNetworkError(Exception):
    """网络连接失败或超时。"""


class OverleafCompileTimeoutError(Exception):
    """编译请求超过等待时限。"""
