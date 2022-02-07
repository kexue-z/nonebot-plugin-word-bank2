import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles as aio
from httpx import AsyncClient, Response


def parse_cmd(pattern, msg: str) -> list:
    return re.findall(pattern, msg, re.S)


def parse_at(msg: str) -> Tuple[str, dict]:
    matcher = re.findall(r"/at\s?([0-9]*)", msg)
    qq_dict = {}
    for qq in matcher:
        qq_dict[f"qq{qq}"] = qq
    msg = re.sub(r"/at\s?([0-9]*)", r"{qq\1:at}", msg)
    return (msg, qq_dict)


def parse_self(msg: str, **kwargs) -> str:
    return parse_at_self(
        re.sub(r"/self", str(kwargs.get("nickname", "")), msg), **kwargs
    )


def parse_at_self(msg: str, **kwargs) -> str:
    sender_id = kwargs.get("sender_id", "")
    if sender_id:
        return re.sub(r"/atself", "{sender_id:at}", msg)
    else:
        return msg


def parse_ban_time(msg: str) -> Optional[int]:
    matcher = re.findall(r"/ban\s?(\d*)", msg)
    if matcher:
        duration = matcher[0]
        # 默认 5 分钟
        return int(duration.strip() or 300)


def parse_ban_msg(msg: str) -> str:
    return re.sub(r"/ban\s?(\d*)", "", msg)


def parse_img(msg: str) -> str:
    return re.sub(r"/img (.*?).image", "{:image}", msg)


def get_message_img(data: str) -> List[Dict[str, str]]:
    """获取消息中的图片数据列表

    Args:
        data (str): event.json()

    Returns:
        List[Dict[str, str]]: [{"url": "http://xxx", "filename": "xxx.image"}]
    """
    try:
        msg_data = []
        data = json.loads(data)
        for msg in data["message"]:
            if msg["type"] == "image":
                msg_data.append(msg["data"])
        return msg_data
    except KeyError:
        return []


async def get_img(url: str) -> Response:
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36 Edg/95.0.1020.53",
    }
    async with AsyncClient() as client:
        res = await client.get(url, headers=headers)
    return res


async def load_image(img_name: List[str]) -> List[bytes]:
    file_list = []
    for img in img_name:
        async with aio.open(img, "rb") as f:
            img = await f.read()
        file_list.append(img)
    return file_list


def file_list_add_path(file_list: List[str], path: Path) -> List[str]:
    for i, file in enumerate(file_list):
        file_list[i] = path / file
    return file_list


def parse_all_msg(msg, **kwargs) -> Tuple[str, dict]:
    a = parse_self(msg, **kwargs)
    b, at = parse_at(a)
    c = parse_img(b)
    return (c, at)


def remove_spaces(msg: str) -> str:
    """去除首尾空白字符"""
    msg = re.sub(r"^(\s*)?", "", msg)
    msg = re.sub(r"(\s*)?$", "", msg)
    return msg
