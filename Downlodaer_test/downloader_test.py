import subprocess
import os
import re
import argparse

# --- НАСТРОЙКИ ---
LINKS_FILE = "links.txt"  # Имя файла со ссылками
# -----------------

def get_best_format(url: str) -> str | None:
    """
    Получает список форматов, находит последний ID типа 'hls-<число>' и возвращает его.
    """
    print(f"\n🔎 Получаю список форматов для видео: {url}")
    try:
        command = ["yt-dlp", "-F", url]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        
        lines = result.stdout.split('\n')
        hls_format_ids = []
        format_regex = re.compile(r"^(?P<id>hls-\d+)\s")

        for line in lines:
            match = format_regex.match(line.strip())
            if match:
                hls_format_ids.append(match.group('id'))

        if not hls_format_ids:
            print("❌ Форматы 'hls-<число>' не найдены для этой ссылки.")
            return None

        best_format_id = hls_format_ids[-1]
        print(f"✅ Найдено лучшее качество (последний в списке 'hls-'): {best_format_id}")
        return best_format_id

    except FileNotFoundError:
        print("❌ ОШИБКА: `yt-dlp` не найден. Убедитесь, что он установлен и доступен в PATH.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ ОШИБКА: yt-dlp вернул ошибку при получении форматов. Возможно, ссылка неверна.")
        print(e.stderr)
        return None
    except Exception as e:
        print(f"❌ Произошла непредвиденная ошибка: {e}")
        return None

def download_video(url: str, format_id: str, threads: int, output_path: str | None, use_fixup: bool):
    """
    Запускает скачивание видео с указанным ID формата, количеством потоков и путем сохранения.
    """
    print(f"🚀 Начинаю загрузку с ID '{format_id}' в {threads} потоков...")
    if use_fixup:
        print("🛠️ Постобработка ffmpeg (fixup) ВКЛЮЧЕНА.")
    else:
        print("🛠️ Постобработка ffmpeg (fixup) ОТКЛЮЧЕНА.")
        
    try:
        command = [
            "yt-dlp",
            "-f", format_id,
            "-N", str(threads),
            url
        ]
        
        if not use_fixup:
            command.extend(["--fixup", "never"])
        
        if output_path:
            if not os.path.exists(output_path):
                print(f"📁 Создаю папку для сохранения: {output_path}")
                os.makedirs(output_path)
            command.extend(["-P", output_path])

        subprocess.run(command, check=True)
        print("✅ Загрузка успешно завершена!")
    except FileNotFoundError:
        print("❌ ОШИБКА: `yt-dlp` не найден. Убедитесь, что он установлен.")
    except subprocess.CalledProcessError:
        print("❌ ОШИБКА: Произошла ошибка во время скачивания.")
    except Exception as e:
        print(f"❌ Произошла непредвиденная ошибка при скачивании: {e}")

def process_url(url: str, threads: int, output_path: str | None, use_fixup: bool):
    """
    Полный процесс обработки одной ссылки: получение формата и скачивание.
    """
    url = url.strip()
    if not url:
        return

    best_format_id = get_best_format(url)
    if best_format_id:
        download_video(url, best_format_id, threads, output_path, use_fixup)


def main():
    """
    Главная функция скрипта.
    """
    # --- УЛУЧШЕННЫЙ БЛОК HELP ---
    parser = argparse.ArgumentParser(
        description="""
Скрипт для автоматического скачивания видео с помощью yt-dlp.

Основная логика работы:
1. Автоматически находит HLS-поток ('hls-<число>') с самым высоким качеством.
2. Скачивает видео в несколько потоков для ускорения процесса.
3. Позволяет гибко настраивать параметры через аргументы командной строки.
4. Источник ссылок: файл 'links.txt' или прямой ввод, если файл пуст.
""",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-p', '--path', 
        type=str, 
        help='Полный путь к папке для сохранения скачанных файлов.\nПример: "C:\\Users\\User\\Downloads"\nЕсли аргумент не указан, файлы сохраняются в ту же папку,\nгде находится скрипт.'
    )
    parser.add_argument(
        '-t', '--threads', 
        type=int, 
        default=6, 
        help='Количество одновременных потоков для скачивания каждого файла.\nБольше потоков может ускорить загрузку, но увеличивает нагрузку на сеть.\n(По умолчанию: 6)'
    )
    parser.add_argument(
        '--use-fixup',
        action='store_true',
        help='Флаг для принудительного включения постобработки видео с помощью ffmpeg.\nЭто может исправить ошибки в контейнере (например, MPEG-TS в MP4),\nно замедляет процесс. По умолчанию эта функция отключена.'
    )
    args = parser.parse_args()
    # --- КОНЕЦ БЛОКА HELP ---

    urls_to_download = []
    if os.path.exists(LINKS_FILE) and os.path.getsize(LINKS_FILE) > 0:
        print(f"📖 Найден файл '{LINKS_FILE}'. Читаю ссылки из него.")
        with open(LINKS_FILE, 'r', encoding='utf-8') as f:
            urls_to_download = [line for line in f if line.strip()]
    
    if not urls_to_download:
        print(f"📝 Файл '{LINKS_FILE}' пуст или не найден.")
        user_url = input("➡️ Введите ссылку на видео для скачивания: ")
        if user_url:
            urls_to_download.append(user_url)

    if not urls_to_download:
        print(" ссылок для скачивания нет. Завершаю работу.")
        return

    print(f"\nНачинаю обработку {len(urls_to_download)} ссылок...")
    print(f"Параметры: Потоков = {args.threads}, Путь = '{args.path or 'Папка со скриптом'}'")
    print("-" * 30)
    
    for url in urls_to_download:
        process_url(url, threads=args.threads, output_path=args.path, use_fixup=args.use_fixup)
        print("-" * 30)
    
    print("🎉 Все задачи выполнены!")


if __name__ == "__main__":
    main()