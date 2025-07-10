import queue
import json

class ServerSentEvent:
    """
    Класс для управления подписчиками и трансляции сообщений
    с использованием Server-Sent Events (SSE).
    Работает как синглтон в рамках одного процесса.
    """
    def __init__(self):
        self.listeners = []

    def subscribe(self):
        """
        Подписывает нового клиента.
        Возвращает очередь, в которую будут поступать сообщения для этого клиента.
        """
        q = queue.Queue(maxsize=5)
        self.listeners.append(q)
        return q

    def unsubscribe(self, q):
        """Отписывает клиента."""
        self.listeners.remove(q)

    def broadcast(self, event_type: str, data: dict):
        """
        Транслирует событие всем подписанным клиентам.
        :param event_type: Название события (например, 'series_updated').
        :param data: Словарь с данными для отправки.
        """
        # Преобразуем данные в JSON строку
        json_data = json.dumps(data)
        
        # Формируем сообщение в формате SSE
        message = f"event: {event_type}\ndata: {json_data}\n\n"
        
        # Помещаем сообщение в очередь каждого активного слушателя
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(message)
            except queue.Full:
                # Если очередь клиента переполнена, удаляем его
                del self.listeners[i]

sse_broadcaster = ServerSentEvent()