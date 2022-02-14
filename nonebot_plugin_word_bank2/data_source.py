import re
import json
from enum import Enum
from pathlib import Path
from functools import lru_cache
from typing import List, Optional, Dict

from nonebot.log import logger


class MatchType(Enum):
    congruence = 1  # 全匹配(==)
    include = 2  # 模糊匹配(in)
    regex = 3  # 正则匹配(regex)


NULL_BANK = {t.name: {"0": {}} for t in MatchType}


class WordBank(object):
    def __init__(self):
        self.data_dir = Path("data/word_bank").absolute()
        self.bank_path = self.data_dir / "bank.json"
        self.img_dir = self.data_dir / "img"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.img_dir.mkdir(parents=True, exist_ok=True)
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
        self.match.cache_clear()

    @lru_cache(100)
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

        # event.to_me 时优先匹配带"/atme "的词条
        if match_type == MatchType.congruence:
            return (bank.get(f"/atme {msg}", []) if to_me else []) or bank.get(msg, [])

        elif match_type == MatchType.include:
            for key in bank:
                if to_me and key.startswith("/atme "):
                    key = key[6:]
                if key in msg:
                    return bank[key]

        elif match_type == MatchType.regex:
            for key in bank:
                if to_me and key.startswith("/atme "):
                    key = key[6:]
                try:
                    if re.search(key, msg, re.S):
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
        return False

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


word_bank = WordBank()
