import socket
import sys
import threading
import re
import configparser
from urllib.parse import urlparse

# Настройки прокси
PROXY_HOST = '127.0.0.1'  # Адрес прокси-сервера
PROXY_PORT = 8080  # Порт прокси-сервера
BUFFER_SIZE = 8192  # Размер буфера для приема данных
TIMEOUT = 10  # Таймаут для сокетов

# Страница блокировки для черного списка
BLOCKED_PAGE_TEMPLATE = """
HTTP/1.1 403 Forbidden
Content-Type: text/html; charset=utf-8
Connection: close

<!DOCTYPE html>
<html>
<head>
    <title>Доступ запрещен</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            text-align: center;
        }}
        .error {{
            color: red;
            font-size: 24px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="error">Доступ запрещен!</div>
    <p>Доступ к ресурсу <b>{url}</b> заблокирован в соответствии с политикой сервера.</p>
</body>
</html>
"""


# Загрузка черного списка из конфигурационного файла
def load_blacklist(config_path="blacklist.conf"):
    blacklist = []
    try:
        config = configparser.ConfigParser()
        config.read(config_path)

        if 'Blacklist' in config:
            for key, value in config['Blacklist'].items():
                if value.lower() == 'true':
                    blacklist.append(key)
    except Exception as e:
        print(f"Ошибка при загрузке черного списка: {e}")

    return blacklist


# Проверка, находится ли URL в черном списке
def is_blacklisted(url, blacklist):
    if not blacklist:
        return False

    parsed_url = urlparse(url)
    host = parsed_url.netloc

    # Удаляем порт из хоста, если он есть
    if ':' in host:
        host = host.split(':')[0]

    # Проверяем домен
    if host in blacklist:
        return True

    # Проверяем полный URL
    for item in blacklist:
        if item == url or (item.startswith('http') and url.startswith(item)):
            return True

    return False


# Обработка клиентского соединения
def handle_client(client_socket, client_addr, blacklist):
    try:
        # Получаем запрос от клиента
        request_data = b''
        while True:
            chunk = client_socket.recv(BUFFER_SIZE)
            request_data += chunk
            if len(chunk) < BUFFER_SIZE or not chunk:
                break

        if not request_data:
            client_socket.close()
            return

        # Парсим первую строку HTTP-запроса
        first_line = request_data.split(b'\n')[0].decode('utf-8', 'ignore')

        # Проверяем, является ли запрос CONNECT-запросом
        connect_match = re.match(r'CONNECT\s+([^\s:]+):(\d+)\s+HTTP/(\d\.\d)', first_line)
        if connect_match:
            # Отправляем сообщение, что HTTPS не поддерживается
            error_response = "HTTP/1.1 501 Not Implemented\r\nContent-Type: text/html\r\n\r\n<h1>501 Not Implemented</h1><p>HTTPS connections are not supported</p>"
            client_socket.send(error_response.encode('utf-8'))
            print(f"HTTPS-соединение отклонено: {first_line}")
            client_socket.close()
            return

        # Обработка обычных HTTP-запросов как раньше
        url_match = re.match(r'(\w+)\s+(http://[^\s]+)\s+HTTP/(\d\.\d)', first_line)

        if not url_match:
            print(f"Некорректный формат запроса: {first_line}")
            client_socket.close()
            return

        method, url, version = url_match.groups()

        # Проверка на черный список
        if is_blacklisted(url, blacklist):
            blocked_page = BLOCKED_PAGE_TEMPLATE.format(url=url).encode('utf-8')
            client_socket.send(blocked_page)
            print(f"{url} - 403 Forbidden (Blacklisted)")
            client_socket.close()
            return

        # Парсим URL
        parsed_url = urlparse(url)
        protocol = parsed_url.scheme
        host = parsed_url.netloc
        path = parsed_url.path

        if not path:
            path = "/"

        if parsed_url.query:
            path += "?" + parsed_url.query

        # Определяем порт
        if ':' in host:
            host, port = host.split(':')
            port = int(port)
        else:
            port = 80  # Стандартный HTTP-порт

        # Создаем соединение с целевым сервером
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(TIMEOUT)

        try:
            server_socket.connect((host, port))

            # Модифицируем запрос для сервера назначения (меняем полный URL на путь)
            modified_request = request_data.decode('utf-8', 'ignore')
            modified_request = modified_request.replace(f"{method} {url}", f"{method} {path}")

            # Отправляем модифицированный запрос серверу
            server_socket.send(modified_request.encode('utf-8'))

            # Получаем ответ от сервера
            response_data = b''

            # Получаем заголовки
            while True:
                chunk = server_socket.recv(BUFFER_SIZE)
                if not chunk:
                    break

                response_data += chunk
                client_socket.send(chunk)

                # Анализируем код ответа после получения первого чанка
                if len(response_data) > 0 and b"HTTP/" in response_data:
                    status_line = response_data.split(b'\n')[0].decode('utf-8', 'ignore')
                    status_match = re.search(r'HTTP/\d\.\d (\d+) ([^\r\n]+)', status_line)
                    if status_match:
                        status_code = status_match.group(1)
                        status_message = status_match.group(2)
                        print(f"{url} - {status_code} {status_message}")

        except socket.error as e:
            print(f"Ошибка при подключении к {host}:{port}: {e}")
            error_response = f"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html\r\n\r\n<h1>502 Bad Gateway</h1><p>Error connecting to {host}:{port}</p>"
            client_socket.send(error_response.encode('utf-8'))
        finally:
            server_socket.close()

    except Exception as e:
        print(f"Ошибка при обработке запроса: {e}")
    finally:
        client_socket.close()


# Основная функция прокси-сервера
def run_proxy_server():
    try:
        # Загружаем черный список
        blacklist = load_blacklist()
        if blacklist:
            print(f"Загружен черный список из {len(blacklist)} элементов")

        # Создаем сокет сервера
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((PROXY_HOST, PROXY_PORT))
        server_socket.listen(100)

        print(f"HTTP прокси-сервер запущен на {PROXY_HOST}:{PROXY_PORT}")

        # Основной цикл прокси-сервера
        while True:
            try:
                client_socket, client_addr = server_socket.accept()
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_addr, blacklist)
                )
                client_thread.daemon = True
                client_thread.start()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Ошибка при обработке соединения: {e}")

    except Exception as e:
        print(f"Ошибка при запуске прокси-сервера: {e}")
    finally:
        print("Завершение работы прокси-сервера")
        server_socket.close()
        sys.exit(0)


if __name__ == "__main__":
    run_proxy_server()
