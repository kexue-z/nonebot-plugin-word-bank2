import json
import os
import re
from pathlib import Path
from typing import List, Optional, Union, Dict

import aiofiles as aio
from nonebot.adapters.onebot.v11 import Message
from nonebot.log import logger

from .util import file_list_add_path, get_img, load_image, parse_all_msg, remove_spaces

OPTIONS = ["congruence", "include", "regex"]

NULL_BANK = dict((option, {"0": {}}) for option in OPTIONS)


class WordBank(object):
    def __init__(self):
        self.data_dir = Path("./").absolute() / "data" / "word_bank"
        self.bank_path = self.data_dir / "bank.json"
        self._img_dir = self.data_dir / "img"
        self.load_bank()

    @property
    def img_dir(self):
        return self._img_dir

    def load_bank(self):
        if (
            os.path.exists(self.data_dir)
            and os.path.isfile(self.bank_path)
            and os.path.exists(self.img_dir)
        ):
            with open(self.bank_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.success("读取词库位于 " + str(self.bank_path))
            self.__data = {key: data.get(key) or {"0": {}} for key in NULL_BANK.keys()}
        else:
            os.makedirs(self.data_dir, exist_ok=True)
            os.makedirs(self.img_dir, exist_ok=True)
            self.__data = NULL_BANK
            self.__save()
            logger.success("创建词库位于 " + str(self.bank_path))

    def match(
        self, index: Union[int, str], msg: str, flags: int = 0, to_me: bool = False
    ) -> Optional[List]:
        """
        匹配词条

        :param index: 为0时是全局词库
        :param msg: 需要匹配的消息
        :param flags:   0: 无限制(默认)
                        1: 全匹配(==)
                        2: 模糊匹配(in)
                        3: 正则匹配(regex)
        :return: 首先匹配成功的消息列表
        """
        msg = remove_spaces(msg)

        if flags:
            return self._match(index, msg, flags, to_me)

        else:
            for type_ in range(1, len(self.__data) + 1):
                re_msg = self._match(index, msg, type_, to_me)
                if re_msg:
                    return re_msg

    def _match(
        self, index: Union[int, str], msg: str, flags: int = 1, to_me: bool = False
    ) -> Optional[List]:
        """
        匹配词条

        :param index: 为0时是全局词库
        :param msg: 需要匹配的消息
        :param flags:   1: 全匹配(==)
                        2: 模糊匹配(in)
                        3: 正则匹配(regex)
        :return: 首先匹配成功的消息列表
        """

        if isinstance(index, int):
            index = str(index)

        type_ = OPTIONS[flags - 1]
        bank: Dict[str, list] = dict(
            self.__data[type_].get(index, {}), **self.__data[type_].get("0", {})
        )

        if flags == 1:
            return (bank.get(f"/atme {msg}", []) if to_me else []) or bank.get(msg, [])

        elif flags == 2:
            for key in bank:
                if (key in f"/atme {msg}" if to_me else False) or key in msg:
                    return bank[key]

        elif flags == 3:
            for key in bank:
                try:
                    if (
                        re.search(key, f"/atme {msg}", re.S) if to_me else False
                    ) or re.search(key, msg, re.S):
                        return bank[key]
                except re.error:
                    logger.error(f"正则匹配错误 - pattern: {key}, string: {msg}")

    def __save(self):
        """
        :return:
        """
        with open(self.bank_path, "w", encoding="utf-8") as f:
            json.dump(self.__data, f, ensure_ascii=False, indent=4)

    def set(self, index: Union[int, str], key: str, value: str, flags: int = 1) -> bool:
        """
        新增词条

        :param index: 为0时是全局词库
        :param key: 触发短语
        :param value: 触发后发送的短语
        :param flags:   1: 全匹配(==)
                        2: 模糊匹配(in)
                        3: 正则匹配(regex)
        :return:
        """
        index = str(index)
        flag = OPTIONS[flags - 1]

        key = remove_spaces(key)
        value = remove_spaces(value)

        logger.debug(f"{index} {key} {value} {flags}")

        if self.__data[flag].get(index, {}):
            if self.__data[flag][index].get(key, []):
                self.__data[flag][index][key].append(value)
            else:
                self.__data[flag][index][key] = [value]
        else:
            self.__data[flag][index] = {key: [value]}

        self.__save()
        return True

    def delete(self, index: Union[int, str], key: str) -> bool:
        """
        删除词条

        :param index: 为0时是全局词库
        :param key: 触发短语
        :return:
        """
        index = str(index)
        flag = False

        for type_ in self.__data:
            if self.__data[type_].get(index, {}).get(key, False):
                del self.__data[type_][index][key]
                flag = True

        self.__save()
        return flag

    def clean(self, index: Union[int, str]) -> bool:
        """
        清空某个对象的词库

        :param index: 为0时是全局词库
        :return:
        """
        index = str(index)
        flag = False

        for type_ in self.__data:
            if self.__data[type_].get(index, {}):
                del self.__data[type_][index]
                flag = True

        self.__save()
        return flag

    def _clean_all(self):
        """
        清空所有词库

        :return:
        """
        self.__data = NULL_BANK
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
            re.findall(r"/img (.*?.image)", msg), self._img_dir
        )
        file_list = await load_image(img_dir_list)
        # msg = re.sub(r"/img (.*?).image", "{:image}", msg)
        msg, at = parse_all_msg(msg, **kwargs)
        return Message.template(msg).format(*file_list, **at, **kwargs)


word_bank = WordBank()
