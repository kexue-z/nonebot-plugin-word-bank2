import json
from pathlib import Path
from typing import List, Optional, Dict

from nonebot.adapters.onebot.v11 import Message
from nonebot.log import logger

from .models import MatchType
from .word_entry import WordEntry
from .util import compare_msg


NULL_BANK = {t.name: {"0": []} for t in MatchType}


class WordBank(object):
    def __init__(self):
        self.data_dir = Path("data/word_bank").absolute()
        self.bank_path = self.data_dir / "bank.json"
        self.img_dir = self.data_dir / "img"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.img_dir.mkdir(parents=True, exist_ok=True)
        self.__data: Dict[str, Dict[str, List[WordEntry]]] = {}
        self.__load()

    def __load(self):
        if self.bank_path.exists() and self.bank_path.is_file():
            with self.bank_path.open("r", encoding="utf-8") as f:
                data: Dict[str, Dict[str, Dict[str, List[str]]]] = json.load(f)
            for t in MatchType:
                self.__data[t.name] = {}
                for user_id in data.get(t.name, {}).keys():
                    self.__data[t.name][user_id] = []
                    for key, value in data[t.name][user_id].items():
                        self.__data[t.name][user_id].append(WordEntry.load(key, value))
            logger.success("读取词库位于 " + str(self.bank_path))
        else:
            self.__data = NULL_BANK
            self.__save()
            logger.success("创建词库位于 " + str(self.bank_path))

    def __save(self):
        data: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        for t in self.__data.keys():
            data[t] = {}
            for user_id in self.__data[t].keys():
                data[t][user_id] = {}
                for entry in self.__data[t][user_id]:
                    key, values = entry.dump()
                    data[t][user_id][key] = values
        with self.bank_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def match(
        self,
        index: str,
        msg: Message,
        match_type: Optional[MatchType] = None,
        to_me: bool = False,
    ) -> List[Message]:
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
            return []
        else:
            return self.__match(index, msg, match_type, to_me)

    def __match(
        self, index: str, msg: Message, match_type: MatchType, to_me: bool = False
    ) -> List[Message]:

        bank: List[WordEntry] = self.__data[match_type.name].get(index, [])
        bank += self.__data[match_type.name].get("0", [])

        for entry in bank:
            if entry.match(msg, match_type, to_me):
                return entry.get_values()
        return []

    def set(
        self,
        index: str,
        match_type: MatchType,
        key: Message,
        value: Message,
        require_to_me: bool = False,
    ) -> bool:
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
        add = False
        if index in self.__data[name]:
            for entry in self.__data[name][index]:
                if entry.require_to_me != require_to_me:
                    continue
                if compare_msg(entry.key, key):
                    entry.add_value(value)
                    add = True
                    break
        else:
            self.__data[name][index] = []
        if not add:
            self.__data[name][index].append(WordEntry(key, [value], require_to_me))
        self.__save()
        return True

    def delete(
        self,
        index: str,
        match_type: MatchType,
        key: Message,
        require_to_me: bool = False,
    ) -> bool:
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
        for entry in list(self.__data[name].get(index, [])):
            if entry.require_to_me != require_to_me:
                continue
            if compare_msg(entry.key, key):
                self.__data[name][index].remove(entry)
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
                if index in self.__data[name]:
                    del self.__data[name][index]
        self.__save()
        return True


word_bank = WordBank()
