"""Единое оформление заголовков экранов и подсказок к подгруппам (Telegram HTML)."""

# Короткий визуальный разделитель (хорошо читается в тёмной и светлой теме)
UI_RULE = "✦ · · · · · · · · · · · · ✦"


def ui_title(emoji: str, title: str) -> str:
    return f"{emoji} <b>{title}</b>"


def ui_intro(text: str) -> str:
    return f"<i>{text}</i>"


def ui_subgroup(icon: str, name: str, hint: str) -> str:
    """Одна подгруппа: иконка, название, краткая подсказка."""
    return f"{icon} <b>{name}</b>\n   ⤷ <i>{hint}</i>"


def ui_screen(*, emoji: str, title: str, intro: str, groups: list[tuple[str, str, str]]) -> str:
    """
    Полный экран: заголовок, разделитель, вводный текст, блоки подгрупп.
    groups: список (иконка, заголовок_подгруппы, подсказка).
    """
    lines = [ui_title(emoji, title), UI_RULE, ui_intro(intro), ""]
    lines.extend(ui_subgroup(ic, nm, ht) for ic, nm, ht in groups)
    return "\n".join(lines)


def ui_panel(*, emoji: str, title: str, intro: str | None, body_lines: list[str]) -> str:
    """Заголовок + опциональный ввод + произвольные строки тела (уже в HTML)."""
    out = [ui_title(emoji, title), UI_RULE]
    if intro:
        out.extend(["", ui_intro(intro), ""])
    else:
        out.append("")
    out.extend(body_lines)
    return "\n".join(out)
