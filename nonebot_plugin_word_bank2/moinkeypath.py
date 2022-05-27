from typing import Any, Optional, Type

from nonebot import __version__ as version
from nonebot.adapters._message import MessageSegment
from nonebot.adapters._template import FormatSpecFunc, MessageTemplate


def format_field(self, value: Any, format_spec: str) -> Any:
    formatter: Optional[FormatSpecFunc] = self.format_specs.get(format_spec)
    if formatter is None and not issubclass(self.factory, str):
        segment_class: Type["MessageSegment"] = self.factory.get_segment_class()
        method = getattr(segment_class, format_spec, None)
        if callable(method):
            formatter = getattr(segment_class, format_spec)
    return (
        super(MessageTemplate, self).format_field(value, format_spec)
        if formatter is None
        else formatter(value)
    )


def monkeypatch():
    if version == "2.0.0b1":
        MessageTemplate.format_field = format_field
