"""Clash 配置构建器：把公共配置与平台配置合并成一份 Mihomo 配置。

用法：
    py scripts/build.py --platform all [--out dist]

合并契约见 docs/REQUIREMENTS.md §11：顶层浅合并，每个顶层键只有一个所有者；
白名单之外的键、公共与平台重复定义的键、同一文件内的重复键都会让构建失败。
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# 公共配置的加载顺序即合并顺序，必须稳定。
COMMON_SOURCES = (
    "general.yaml",
    "proxies.yaml",
    "proxy-groups.yaml",
    "dns.yaml",
    "rules.yaml",
)

# 公共独占的顶层键。
COMMON_KEYS = (
    "mode",
    "log-level",
    "ipv6",
    "proxies",
    "proxy-groups",
    "dns",
    "rules",
)

# 每个平台独占的顶层键（docs/REQUIREMENTS.md §11）。
PLATFORM_KEYS = {
    "windows": ("mixed-port", "allow-lan", "tun"),
    "openclash": ("port", "allow-lan", "bind-address"),
}

# 输出键的固定顺序：相同输入必须产生字节一致的输出（§11 约束 5）。
KEY_ORDER = (
    "mode",
    "log-level",
    "ipv6",
    "mixed-port",
    "port",
    "allow-lan",
    "bind-address",
    "tun",
    "dns",
    "proxies",
    "proxy-groups",
    "rules",
)


class ConfigError(Exception):
    """配置不满足合并契约或无法解析。"""


class _UniqueKeyLoader(yaml.SafeLoader):
    """拒绝重复键的 SafeLoader：PyYAML 默认静默保留后一个值。"""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigError("重复的键 %r" % (key,))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def load_yaml_file(path):
    """读取 YAML 文件，任何解析问题都转换为带文件名的 ConfigError。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError("无法读取配置文件 %s：%s" % (path, exc)) from exc
    loader = _UniqueKeyLoader(text)
    try:
        data = loader.get_single_data()
    except ConfigError as exc:
        raise ConfigError("%s：%s" % (path, exc)) from exc
    except yaml.YAMLError as exc:
        raise ConfigError("%s：YAML 解析失败：%s" % (path, exc)) from exc
    finally:
        loader.dispose()
    if data is None:
        raise ConfigError("%s：文件为空" % path)
    if not isinstance(data, dict):
        raise ConfigError("%s：顶层必须是映射" % path)
    return data


def _merge_source(merged, owners, path, allowed_keys):
    data = load_yaml_file(path)
    for key in data:
        if key not in allowed_keys:
            raise ConfigError(
                "%s：未登记的顶层键 %r（允许：%s）"
                % (path, key, ", ".join(allowed_keys))
            )
        if key in merged:
            raise ConfigError(
                "顶层键 %r 重复定义：%s 与 %s" % (key, owners[key], path)
            )
        merged[key] = data[key]
        owners[key] = path


def build_platform(platform, root=REPO_ROOT):
    """合并公共配置与指定平台配置，返回按键顺序排列的配置字典。"""
    if platform not in PLATFORM_KEYS:
        raise ConfigError(
            "未知平台 %r，可用平台：%s" % (platform, ", ".join(sorted(PLATFORM_KEYS)))
        )
    root = Path(root)
    merged = {}
    owners = {}
    for name in COMMON_SOURCES:
        _merge_source(merged, owners, root / "configs" / "common" / name, COMMON_KEYS)
    _merge_source(
        merged,
        owners,
        root / "configs" / platform / "platform.yaml",
        PLATFORM_KEYS[platform],
    )

    required = set(COMMON_KEYS) | set(PLATFORM_KEYS[platform])
    missing = sorted(required - set(merged))
    if missing:
        raise ConfigError("缺少顶层键：%s" % ", ".join(missing))

    return {key: merged[key] for key in KEY_ORDER if key in merged}


def dump_yaml(cfg):
    """把配置序列化为 UTF-8 文本；键顺序固定，不含时间戳。"""
    return yaml.safe_dump(
        cfg,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=4096,
    )


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="构建 Clash/Mihomo 配置")
    parser.add_argument(
        "--platform", required=True, choices=["all", "windows", "openclash"]
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT,
        help="源文件根目录（默认为仓库根目录）",
    )
    args = parser.parse_args(argv)

    targets = tuple(PLATFORM_KEYS) if args.platform == "all" else (args.platform,)
    try:
        rendered = {
            platform: dump_yaml(build_platform(platform, args.root))
            for platform in targets
        }
    except ConfigError as exc:
        print("构建失败：%s" % exc, file=sys.stderr)
        return 2

    for platform, text in rendered.items():
        directory = args.out / platform
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "config.yaml"
        path.write_text(text, encoding="utf-8", newline="\n")
        print("已生成 %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
