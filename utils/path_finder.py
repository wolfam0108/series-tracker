import os
import sys

def get_executable_path(name: str) -> str:
    """
    Находит полный путь к исполняемому файлу (например, 'yt-dlp' или 'ffmpeg').
    Приоритет отдается файлу внутри виртуального окружения (venv).
    
    :param name: Имя исполняемого файла.
    :return: Абсолютный путь к файлу или просто имя, если он должен быть в системном PATH.
    """
    # sys.executable - это путь к интерпретатору python (например, /home/user/project/venv/bin/python)
    # os.path.dirname(...) дает нам папку /home/user/project/venv/bin/
    venv_executable_path = os.path.join(os.path.dirname(sys.executable), name)
    
    if os.path.exists(venv_executable_path):
        # Если нашли исполняемый файл рядом с python в venv, используем его абсолютный путь
        return venv_executable_path
    else:
        # Если нет, полагаемся на системный PATH (для локального запуска)
        return name