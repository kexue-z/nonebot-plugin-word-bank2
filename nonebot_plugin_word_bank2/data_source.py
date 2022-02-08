import json
import re
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict

import aiofiles as aio
from nonebot.adapters.onebot.v11 import Message
from nonebot.log import logger

from .util import file_list_add_path, get_img, load_image, parse_all_msg


class MatchType(Enum):
    congruence = 1
    include = 2
    regex = 3


NULL_BANK = {t.name: {"0": {}} for t in MatchType}


class WordBank(object):
    def __init__(self):
        self.data_dir = Path("data/word_bank").absolute()
        self.bank_path = self.data_dir / "bank.json"
        self.img_dir = self.data_dir / "img"
        self.data_dir.mkdir(exist_ok=True)
        self.img_dir.mkdir(exist_ok=True)
        self.__data: Dict[str, Dict[str, Dict[str, list]]] = {}
        self.__load()

    def __load(self):
        if self.bank_path.exists() and self.bank_path.is_file():
            with self.bank_path.open("r", encoding="utf-8") as f:
                data: dict = json.load(f)
            self.__data = {t.name: data.get(t.name) or {"0": {}} for t in MatchType}
            logger.success("读取词库位于 " + str(self.bank_path))
        else:
            self.__data = NULL_BANK
            self.__save()
            logger.success("创建词库位于 " + str(self.bank_path))

    def __save(self):
        with self.bank_path.open("w", encoding="utf-8") as f:
            json.dump(self.__data, f, ensure_ascii=False, indent=4)

    def match(
        self,
        index: str,
        msg: str,
        match_type: Optional[MatchType] = None,
        to_me: bool = False,
    ) -> Optional[List]:
        """
        匹配词条

        :param index: 为0时是全局词库
        :param msg: 需要匹配的消息
        :param match_type: 为空表示依次尝试所有匹配方式
                           MatchType.congruence: 全匹配(==)
                           MatchType.include: 模糊匹配(in)
                           MatchType.regex: 正则匹配(regex)
        :return: 首先匹配成功的消息列表
        """
        if match_type is None:
            for type_ in MatchType:
                res = self.__match(index, msg, type_, to_me)
                if res:
                    return res
        else:
            return self.__match(index, msg, match_type, to_me)

    def __match(
        self, index: str, msg: str, match_type: MatchType, to_me: bool = False
    ) -> Optional[List]:

        bank: Dict[str, list] = dict(
            self.__data[match_type.name].get(index, {}),
            **self.__data[match_type.name].get("0", {}),
        )

        if match_type == MatchType.congruence:
            return (bank.get(f"/atme {msg}", []) if to_me else []) or bank.get(msg, [])

        elif match_type == MatchType.include:
            for key in bank:
                if (key in f"/atme {msg}" if to_me else False) or key in msg:
                    return bank[key]

        elif match_type == MatchType.regex:
            for key in bank:
                try:
                    if (
                        re.search(key, f"/atme {msg}", re.S) if to_me else False
                    ) or re.search(key, msg, re.S):
                        return bank[key]
                except re.error:
                    logger.error(f"正则匹配错误 - pattern: {key}, string: {msg}")

    def set(self, index: str, key: str, value: str, match_type: MatchType) -> bool:
        """
        新增词条

        :param index: 为0时是全局词库
        :param key: 触发短语
        :param value: 触发后发送的短语
        :param match_type: MatchType.congruence: 全匹配(==)
                           MatchType.include: 模糊匹配(in)
                           MatchType.regex: 正则匹配(regex)
        :return:
        """
        name = match_type.name
        if self.__data[name].get(index, {}):
            if self.__data[name][index].get(key, []):
                self.__data[name][index][key].append(value)
            else:
                self.__data[name][index][key] = [value]
        else:
            self.__data[name][index] = {key: [value]}

        self.__save()
        return True

    def delete(self, index: str, key: str, match_type: MatchType) -> bool:
        """
        删除词条

        :param index: 为0时是全局词库
        :param key: 触发短语
        :param match_type: MatchType.congruence: 全匹配(==)
                           MatchType.include: 模糊匹配(in)
                           MatchType.regex: 正则匹配(regex)
        :return:
        """
        name = match_type.name
        if self.__data[name].get(index, {}).get(key, False):
            del self.__data[name][index][key]

        self.__save()
        return True

    def clear(self, index: str) -> bool:
        """
        清空某个对象的词库

        :param index: 为0时是全局词库, 为空时清空所有词库
        :return:
        """
        if index is None:
            self.__data = NULL_BANK
        else:
            for type_ in MatchType:
                name = type_.name
                if self.__data[name].get(index, {}):
                    del self.__data[name][index]

        self.__save()
        return True

    async def save_img(self, img: bytes, filename: str) -> None:
        async with aio.open(str(self.img_dir / filename), "wb") as f:
            await f.write(img)

    async def load_img(self, filename: str) -> bytes:
        async with aio.open(str(self.img_dir / filename), "rb") as f:
            return await f.read()

    async def convert_and_save_img(self, img_list: list, raw_message: str) -> str:
        """将图片保存,并将图片替换为图片名字

        Args:
            img_list (list): Meassage 中所有的图片列表 [{"url": "http://xxx", "filename": "xxx.image"}]
            raw_message (str): [event.raw_message

        Returns:
            str: 转换后的raw_message
        """
        # 保存图片
        for img in img_list:
            res = await get_img(img["url"])
            await self.save_img(res.content, img["file"])
        # 将图片的位置替换为 /img xxx.image
        return re.sub(
            r"\[CQ:image.*?file=(.*).image.*?]", r"/img \1.image", raw_message
        )

    async def parse_msg(self, msg, **kwargs) -> Message:
        img_dir_list = file_list_add_path(
            re.findall(r"/img (.*?.image)", msg), self.img_dir
        )
        file_list = await load_image(img_dir_list)
        # msg = re.sub(r"/img (.*?).image", "{:image}", msg)
        msg, at = parse_all_msg(msg, **kwargs)
        return Message.template(msg).format(*file_list, **at, **kwargs)


word_bank = WordBank()
