"""Перезапуск процесса бота после штатной остановки polling (os.execl)."""
import os
import sys

from data.config import BASE_DIR

_restart_flag = False


def mark_restart_requested() -> None:
    global _restart_flag
    _restart_flag = True


def cancel_restart_request() -> None:
    global _restart_flag
    _restart_flag = False


def consume_restart_request() -> bool:
    global _restart_flag
    if not _restart_flag:
        return False
    _restart_flag = False
    return True


def perform_execl_restart() -> None:
    """Заменяет текущий процесс новым экземпляром satana.py. Не возвращается."""
    script = os.path.join(BASE_DIR, "satana.py")
    os.chdir(BASE_DIR)
    os.execl(sys.executable, sys.executable, script)
