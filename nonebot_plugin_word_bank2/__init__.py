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
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, RegexGroup, State
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State, T_Handler

from .data_source import word_bank as wb
from .util import (
    get_message_img,
    parse_ban_msg,
    parse_ban_time,
)

reply_type = "random"

export().word_bank = wb


def get_session_id(event: MessageEvent) -> str:
    if isinstance(event, GroupMessageEvent):
        return f"group_{event.group_id}"
    else:
        return f"private_{event.user_id}"


wb_matcher = on_message(priority=99)


@wb_matcher.handle()
async def handle_wb(bot: Bot, event: MessageEvent):
    index = get_session_id(event)
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
    index = get_session_id(event)

    flag, key, value = matched
    type_ = 3 if "正则" in flag else 2 if "模糊" in flag else 1
    if "@" in flag:
        key = "/atme " + key
    else:
        for name in bot.config.nickname:
            if key.startswith(name):
                key = key.replace(name, "/atme ", 1)
                break

    pic_data = get_message_img(event.json())
    if pic_data and ("CQ:image" not in key):
        # 如果回答中含有图片 则保存图片 并将图片替换为 /img xxx.image
        value = await wb.convert_and_save_img(pic_data, value)

    res = wb.set("0" if "全局" in flag else index, unescape(key), value, type_)
    if res:
        await wb_set_cmd.finish(message="我记住了~")


wb_del_cmd = on_command(
    "删除词条",
    block=True,
    permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND,
)


@wb_del_cmd.handle()
async def _(event: MessageEvent, arg: Message = CommandArg()):
    await wb_del(wb_del_cmd, get_session_id(event), arg)


wb_del_admin = on_command(
    "删除全局词条",
    block=True,
    permission=SUPERUSER,
)


@wb_del_admin.handle()
async def _(arg: Message = CommandArg()):
    await wb_del(wb_del_cmd, "0", arg)


async def wb_del(matcher: Matcher, index: str, arg: Message):
    msg = arg.extract_plain_text().strip()
    if msg:
        res = wb.delete(index, unescape(msg))
        if res:
            await matcher.finish(message="删除成功~")


def wb_del_all(type_: str = None) -> T_Handler:
    async def wb_del_all_(
        event: MessageEvent, arg: Message = CommandArg(), state: T_State = State()
    ):
        msg = arg.extract_plain_text().strip()
        if msg:
            state["is_sure"] = msg

        if not type_:
            index = get_session_id(event)
            keyword = "群聊" if isinstance(event, GroupMessageEvent) else "个人"
        else:
            index = "0" if type_ == "全局" else None
            keyword = type_
        state["index"] = index
        state["keyword"] = keyword

    return wb_del_all_


wb_del_all_cmd = on_command(
    "删除词库",
    block=True,
    permission=SUPERUSER | GROUP_OWNER | PRIVATE_FRIEND,
    handlers=[wb_del_all()],
)
wb_del_all_admin = on_command(
    "删除全局词库", block=True, permission=SUPERUSER, handlers=[wb_del_all("全局")]
)
wb_del_all_bank = on_command(
    "删除全部词库", block=True, permission=SUPERUSER, handlers=[wb_del_all("全部")]
)


prompt_clean = Message.template("此命令将会清空您的{keyword}词库，确定请发送 yes")


@wb_del_all_cmd.got("is_sure", prompt=prompt_clean)
@wb_del_all_admin.got("is_sure", prompt=prompt_clean)
@wb_del_all_bank.got("is_sure", prompt=prompt_clean)
async def _(matcher: Matcher, state: T_State = State()):
    is_sure = str(state["is_sure"]).strip()
    index = state["index"]
    if is_sure == "yes":
        res = wb.clean(index)
        if res:
            await matcher.finish(Message.template("删除{keyword}词库成功~"))
    else:
        await matcher.finish("命令取消")
