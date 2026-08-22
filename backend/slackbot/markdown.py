"""Markdown → Slack mrkdwn conversion for agent answers.

The models write GitHub-flavored markdown; Slack renders its own mrkdwn
dialect. Only the constructs that actually look broken in Slack are
rewritten — bold, links, and headings. Everything else (backticks,
bullets, blockquotes) already renders acceptably.
"""
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def to_mrkdwn(text: str) -> str:
    text = _BOLD.sub(r"*\1*", text)
    text = _LINK.sub(r"<\2|\1>", text)
    text = _HEADING.sub(r"*\1*", text)
    return text
