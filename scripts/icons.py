"""策略组图标：把 assets/icons/*.png 内联为 base64 data URI。

设计约束（2026-11-14 负责人确认）：
- 图标使用 Qure 图标集（PNG），不再使用 SVG；仓库存 PNG 源文件，构建期内联。
- 产物不依赖网络，可离线部署、可复现；图标只影响展示，不参与分流。
- 文件名由 proxy-groups.yaml 的 icon 字段引用。
"""

import base64
import re
from pathlib import Path

ICON_DIR = Path("assets") / "icons"
ICON_SUFFIX = ".png"
MAX_ICON_BYTES = 16 * 1024
ICON_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATA_URI_PREFIX = "data:image/png;base64,"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconError(Exception):
    """图标缺失、命名非法或内容不是 PNG。"""


def icon_path(name, root):
    """返回图标源文件路径；名称非法时立即报错。"""
    if not isinstance(name, str) or not ICON_NAME_PATTERN.match(name):
        raise IconError("图标名称必须匹配 %s：%r" % (ICON_NAME_PATTERN.pattern, name))
    return Path(root) / ICON_DIR / (name + ICON_SUFFIX)


def load_icon(name, root):
    """读取 PNG 源文件并返回可直接写入配置的 data URI。"""
    path = icon_path(name, root)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise IconError("无法读取图标 %s：%s" % (path, exc)) from exc
    if not data:
        raise IconError("图标为空：%s" % path)
    if len(data) > MAX_ICON_BYTES:
        raise IconError(
            "图标超过 %d 字节：%s（%d 字节）" % (MAX_ICON_BYTES, path, len(data))
        )
    if not data.startswith(PNG_SIGNATURE):
        raise IconError("图标不是 PNG：%s" % path)
    return DATA_URI_PREFIX + base64.b64encode(data).decode("ascii")


def load_icons(names, root):
    """批量加载，返回 name -> data URI 的映射。"""
    return {name: load_icon(name, root) for name in names}
