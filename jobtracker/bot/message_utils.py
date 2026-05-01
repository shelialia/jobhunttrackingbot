from telegram import Bot, Message
from telegram.constants import ParseMode


MAX_TELEGRAM_TEXT = 3500


def _split_long_line(line: str, max_len: int) -> list[str]:
    if max_len <= 0:
        return [line]

    parts: list[str] = []
    remaining = line
    while len(remaining) > max_len:
        split_at = remaining.rfind(" ", 0, max_len)
        if split_at <= 0:
            split_at = max_len
        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    parts.append(remaining)
    return parts


def chunk_lines(
    lines: list[str],
    *,
    prefix: str = "",
    suffix: str = "",
    max_len: int = MAX_TELEGRAM_TEXT,
) -> list[str]:
    available = max_len - len(prefix) - len(suffix)
    if available <= 0:
        return [prefix + suffix]

    chunks: list[str] = []
    current_lines: list[str] = []

    for line in lines:
        for part in _split_long_line(line, available):
            candidate_lines = current_lines + [part]
            candidate = prefix + "\n".join(candidate_lines) + suffix
            if current_lines and len(candidate) > max_len:
                chunks.append(prefix + "\n".join(current_lines) + suffix)
                current_lines = [part]
            else:
                current_lines = candidate_lines

    if current_lines or not chunks:
        chunks.append(prefix + "\n".join(current_lines) + suffix)

    return chunks


async def reply_chunked_lines(
    message: Message,
    lines: list[str],
    *,
    parse_mode: str | ParseMode | None = None,
    reply_markup=None,
    prefix: str = "",
    suffix: str = "",
    max_len: int = MAX_TELEGRAM_TEXT,
) -> None:
    chunks = chunk_lines(lines, prefix=prefix, suffix=suffix, max_len=max_len)
    for idx, chunk in enumerate(chunks):
        await message.reply_text(
            chunk,
            parse_mode=parse_mode,
            reply_markup=reply_markup if idx == len(chunks) - 1 else None,
        )


async def send_chunked_lines(
    bot: Bot,
    chat_id: int,
    lines: list[str],
    *,
    parse_mode: str | ParseMode | None = None,
    reply_markup=None,
    prefix: str = "",
    suffix: str = "",
    max_len: int = MAX_TELEGRAM_TEXT,
) -> None:
    chunks = chunk_lines(lines, prefix=prefix, suffix=suffix, max_len=max_len)
    for idx, chunk in enumerate(chunks):
        await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode=parse_mode,
            reply_markup=reply_markup if idx == len(chunks) - 1 else None,
        )
