import tempfile
import json
import os
import copy
import re
from typing import Any

def extract_single_json_from_text(text: str):
    if not isinstance(text, str):
        return None

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\{\[]", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        return value

    return None


def read_json(path: str) -> dict:
    """
    读取 JSON 文件并返回 Python 字典。

    :param path: JSON 文件的绝对路径
    :return: 解析后的 Python 字典
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: str, data: dict, indent: int = 2) -> None:
    """
    将 Python 字典写回 JSON 文件（原子性写入，防止写入中断导致文件损坏）。

    :param path: JSON 文件的绝对路径
    :param data: 要写入的 Python 字典
    :param indent: JSON 缩进空格数，默认 2
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    with tempfile.NamedTemporaryFile('w', dir=dir_name,
                                     delete=False, encoding='utf-8') as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=indent)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


# 1. 根据键名模式查找路径
def find_keys_by_pattern(python_dict: dict, name_pattern: str):
    matches = []
    pattern = re.compile(rf"^{re.escape(name_pattern)}")

    def dfs(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = f"{path}.{k}" if path else k
                if pattern.match(k):
                    matches.append(new_path)
                dfs(v, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                dfs(item, new_path)

    dfs(python_dict, "")
    return matches


# 2. 根据路径获取值
def get_value_by_path_without_copy(python_dict: dict, key_path: str):
    parts = re.split(r"(?<!\])\.", key_path)
    obj = python_dict

    for part in parts:
        m = re.match(r"(\w+)(\[(\d+)\])?", part)
        if not m:
            raise ValueError(f"Invalid path segment: {part}")

        key = m.group(1)
        index = m.group(3)

        obj = obj[key]
        if index is not None:
            obj = obj[int(index)]

    # 深拷贝：返回独立副本，修改不影响原字典
    return copy.deepcopy(obj)


def get_value_by_path_with_copy(python_dict: dict, key_path: str):
    parts = re.split(r"(?<!\])\.", key_path)  # 支持 list 索引
    obj = python_dict

    for part in parts:
        m = re.match(r"(\w+)(\[(\d+)\])?", part)
        if not m:
            raise ValueError(f"Invalid path segment: {part}")

        key = m.group(1)
        index = m.group(3)

        obj = obj[key]
        if index is not None:
            obj = obj[int(index)]

    return obj


# 3. 根据路径设置（修改）值（路径必须存在）
def set_value_by_path(python_dict: dict, key_path: str, new_value: any):
    parts = re.split(r"(?<!\])\.", key_path)
    obj = python_dict

    for i, part in enumerate(parts):
        m = re.match(r"(\w+)(\[(\d+)\])?", part)
        key = m.group(1)
        index = m.group(3)

        if i == len(parts) - 1:  # 最后一级
            if index is None:
                obj[key] = new_value
            else:
                obj[key][int(index)] = new_value
            return

        obj = obj[key]
        if index is not None:
            obj = obj[int(index)]


# 4. 根据路径自动创建并添加值
def add_value_by_path(python_dict: dict, key_path: str, key_name: str, key_value: any):
    parts = key_path.split(".")
    obj = python_dict

    # 自动创建中间 dict
    for p in parts:
        if p not in obj or not isinstance(obj[p], dict):
            obj[p] = {}
        obj = obj[p]

    # 添加键值
    obj[key_name] = key_value


# 5. 删除路径对应的 key
def delete_by_path(python_dict, key_path):
    parts = re.split(r"(?<!\])\.", key_path)
    obj = python_dict

    for i, part in enumerate(parts):
        m = re.match(r"(\w+)(\[(\d+)\])?", part)
        key = m.group(1)
        index = m.group(3)

        # 最后一级：删除
        if i == len(parts) - 1:
            if index is None:
                return obj.pop(key, None) is not None
            else:
                arr = obj[key]
                idx = int(index)
                if 0 <= idx < len(arr):
                    arr.pop(idx)
                    return True
                return False

        obj = obj[key]
        if index is not None:
            obj = obj[int(index)]
