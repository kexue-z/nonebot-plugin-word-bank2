import random
from typing import Tuple
from nonebot import export, on_command, on_message, on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent
from nonebot.adapters.onebot.v11.permission import (
    GROUP_ADMIN,
    GROUP_OWNER,
    PRIVATE_FRIEND,
)
from nonebot.adapters.onebot.v11.utils import unescape
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, RegexGroup, ArgPlainText
from nonebot.permission import SUPERUSER

from .data_source import word_bank as wb
from .util import (
    get_message_img,
    parse_ban_msg,
    parse_ban_time,
)

reply_type = "random"

export().word_bank = wb

wb_matcher = on_message(priority=99)


@wb_matcher.handle()
async def handle_wb(bot: Bot, event: MessageEvent):
    if isinstance(event, GroupMessageEvent):
        index = event.group_id
    else:
        index = event.user_id

    msgs = wb.match(index, unescape(str(event.get_message())), to_me=event.is_tome())
    if not msgs:
        wb_matcher.block = False
        await wb_matcher.finish()
    wb_matcher.block = True

    if reply_type == "random":
        msgs = [random.choice(msgs)]

    for msg in msgs:
        duration = parse_ban_time(msg)

        if duration and isinstance(event, GroupMessageEvent):
            msg = parse_ban_msg(msg)
            await bot.set_group_ban(
                group_id=event.group_id,
                user_id=event.user_id,
                duration=duration,
            )

        await wb_matcher.finish(
            await wb.parse_msg(
                msg=msg,
                nickname=event.sender.card or event.sender.nickname,
                sender_id=event.sender.user_id,
            )
        )


wb_set_cmd = on_regex(
    r"^((?:全局|模糊|正则|@)*)\s*问\s?(.+?)\s?答\s?(.+)",
    block=True,
    permission=GROUP_ADMIN | GROUP_OWNER | PRIVATE_FRIEND | SUPERUSER,
)


@wb_set_cmd.handle()
async def wb_set(
    bot: Bot, event: MessageEvent, matched: Tuple[str, ...] = RegexGroup()
):

    if isinstance(event, GroupMessageEvent):
        index = event.group_id
    else:
        index = event.user_id

    pic_data = get_message_img(event.json())

    flag, key, value = matched
    type_ = 3 if "正则" in flag else 2 if "模糊" in flag else 1
    if "@" in flag:
        key = "/atme " + key
    else:
        for name in bot.config.nickname:
            if key.startswith(name):
                key = key.replace(name, "/atme ", 1)
                break

    if pic_data and ("CQ:image" not in key):
        # 如果回答中含有图片 则保存图片 并将图片替换为 /img xxx.image
        value = await wb.convert_and_save_img(pic_data, value)

    res = wb.set(0 if "全局" in flag else index, unescape(key), value, type_)
    if res:
        await wb_set_cmd.finish(message="我记住了~")


wb_del_cmd = on_command(
    "删除词条",
    block=True,
    permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND,
)


@wb_del_cmd.handle()
async def wb_del_(event: MessageEvent, arg: Message = CommandArg()):
    logger.debug(isinstance(event, GroupMessageEvent))

    if isinstance(event, GroupMessageEvent):
        index = event.group_id
    else:
        index = event.user_id

    logger.debug(index)

    msg = arg.extract_plain_text()

    logger.debug(msg)
    res = wb.delete(index, unescape(msg))
    if res:
        await wb_del_cmd.finish(message="删除成功~")


wb_del_admin = on_command(
    "删除全局词条",
    block=True,
    permission=SUPERUSER,
)


@wb_del_admin.handle()
async def wb_del_admin_(arg: Message = CommandArg()):
    msg = arg.extract_plain_text().strip()
    if msg:
        res = wb.delete(0, unescape(msg))
        if res:
            await wb_del_admin.finish(message="删除成功~")


async def wb_del_all(matcher: Matcher, arg: Message = CommandArg()):
    msg = arg.extract_plain_text().strip()
    if msg:
        matcher.set_arg("is_sure", Message(msg))


wb_del_all_cmd = on_command(
    "删除词库",
    block=True,
    permission=SUPERUSER | GROUP_OWNER | PRIVATE_FRIEND,
    handlers=[wb_del_all],
)
wb_del_all_admin = on_command(
    "删除全局词库", block=True, permission=SUPERUSER, handlers=[wb_del_all]
)
wb_del_all_bank = on_command(
    "删除全部词库", block=True, permission=SUPERUSER, handlers=[wb_del_all]
)


@wb_del_all_cmd.got("is_sure", prompt="此命令将会清空您的群聊/私人词库，确定请发送 yes")
async def wb_del_all_(event: MessageEvent, is_sure: str = ArgPlainText()):
    if is_sure == "yes":

        if isinstance(event, GroupMessageEvent):
            res = wb.clean(event.group_id)
            if res:
                await wb_del_all_cmd.finish("删除群聊词库成功~")
        else:
            res = wb.clean(event.user_id)
            if res:
                await wb_del_all_cmd.finish("删除个人词库成功~")

    else:
        await wb_del_all_cmd.finish("命令取消")


@wb_del_all_admin.got("is_sure", prompt="此命令将会清空您的全局词库，确定请发送 yes")
async def wb_del_all_admin_(is_sure: str = ArgPlainText()):
    if is_sure == "yes":
        res = wb.clean(0)
        if res:
            await wb_del_all_admin.finish("删除全局词库成功~")
    else:
        await wb_del_all_admin.finish("命令取消")


@wb_del_all_bank.got("is_sure", prompt="此命令将会清空您的全部词库，确定请发送 yes")
async def wb_del_all_bank_(is_sure: str = ArgPlainText()):
    if is_sure == "yes":
        res = wb._clean_all()
        if res:
            await wb_del_all_bank.finish("删除全部词库成功~")
    else:
        await wb_del_all_bank.finish("命令取消")
