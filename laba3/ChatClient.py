import socket
import sys
from threading import Thread, Event
import time
import signal


class ChatClient:
    def __init__(self):
        self.username = input("Введите ваше имя: ").strip()
        self.client_ip = self.get_valid_client_ip()
        self.server_address = self.get_valid_server_ip()
        self.server_port = self.get_valid_port("сервера")
        self.client_port = self.get_valid_port("клиента")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.exit_event = Event()
        self.connected = False

        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            self.socket.bind((self.client_ip, self.client_port))
            # Устанавливаем таймаут для сокета
            self.socket.settimeout(5.0)
            self.connected = True
            print(f"\n{self.username}, вы подключены через {self.client_ip}:{self.client_port}")
            print("Введите сообщение (выход - 'exit'):\n")
        except socket.error as e:
            print(f"Ошибка привязки к {self.client_ip}:{self.client_port}: {e}")
            sys.exit(1)

    def handle_shutdown(self, signum, frame):
        """Обработчик сигналов завершения"""
        print("\nПолучен сигнал завершения. Отключение...")
        self.disconnect()

    def disconnect(self):
        """Корректное отключение клиента"""
        if self.connected:
            try:
                self.socket.sendto(b'exit', (self.server_address, self.server_port))
            except:
                pass  # Игнорируем ошибки при завершении

        self.exit_event.set()
        time.sleep(0.2)

        try:
            self.socket.close()
        except:
            pass

        self.connected = False
        print("\nОтключение от сервера завершено")

    def get_valid_client_ip(self):
        print("Доступные IP-адреса на вашем устройстве:")
        host_name = socket.gethostname()
        ip_list = socket.gethostbyname_ex(host_name)[2]
        ip_list.append('127.0.0.1')

        for i, ip in enumerate(ip_list, 1):
            print(f"{i}. {ip}")

        while True:
            choice = input("Выберите номер IP или введите свой IP-адрес: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(ip_list):
                return ip_list[int(choice) - 1]

            # Проверка введенного IP
            if choice:
                parts = choice.split(".")
                if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                    try:
                        socket.inet_aton(choice)
                        return choice
                    except socket.error:
                        pass
            print("Некорректный IP. Пожалуйста, выберите из списка или введите правильный IP-адрес.")

    def get_valid_server_ip(self):
        ip = input("Введите IP сервера (по умолчанию '127.0.0.1'): ").strip()
        if not ip:
            ip = '127.0.0.1'  # Устанавливаем локальный IP, если ничего не введено
        parts = ip.split(".")
        while len(parts) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
            print("Некорректный IP. Пожалуйста, введите правильный IP-адрес.")
            ip = input("IP сервера (по умолчанию '127.0.0.1'): ").strip()
            if not ip:
                ip = '127.0.0.1'
            parts = ip.split(".")
        return ip

    def get_valid_port(self, target):
        while True:
            try:
                port = int(input(f"Введите порт {target} (1024-65535): "))
                if 1024 <= port <= 65535:
                    return port
                print("Порт должен быть в диапазоне 1024-65535")
            except ValueError:
                print("Введите число")

    def listen_for_messages(self):
        consecutive_timeouts = 0
        max_timeouts = 5  # Максимальное количество таймаутов подряд

        while not self.exit_event.is_set():
            try:
                data, _ = self.socket.recvfrom(1024)
                message = data.decode()
                print(message)

                # Если сервер сообщает о закрытии, отключаемся
                if message == "Сервер закрывается. Соединение будет прервано.":
                    print("\nСервер закрылся. Отключение...")
                    self.exit_event.set()
                    break

                # Сбрасываем счетчик таймаутов при успешном получении сообщения
                consecutive_timeouts = 0

            except socket.timeout:
                # Увеличиваем счетчик таймаутов
                consecutive_timeouts += 1

                # Если слишком много таймаутов подряд, проверяем соединение с сервером
                if consecutive_timeouts >= max_timeouts:
                    try:
                        # Отправляем проверочное сообщение
                        self.socket.sendto(b'ping', (self.server_address, self.server_port))
                        consecutive_timeouts = 0
                    except socket.error:
                        if not self.exit_event.is_set():
                            print("\nПотеряно соединение с сервером. Возможно, сервер недоступен.")
                            self.exit_event.set()
                            break
            except ConnectionResetError:
                if not self.exit_event.is_set():
                    print("\nСоединение сброшено сервером")
                    self.exit_event.set()
                    break
            except socket.error as e:
                if not self.exit_event.is_set():
                    print(f"\nОшибка соединения: {e}")
                    self.exit_event.set()
                    break

    def run(self):
        # Запускаем поток для прослушивания сообщений
        listener_thread = Thread(target=self.listen_for_messages, daemon=True)
        listener_thread.start()

        # Отправляем регистрационное сообщение с добавлением IP клиента
        try:
            self.socket.sendto(f"reg:{self.username}:{self.client_ip}".encode(),
                               (self.server_address, self.server_port))
        except socket.error as e:
            print(f"Ошибка при регистрации: {e}")
            print("Сервер недоступен. Попробуйте позже.")
            self.disconnect()
            return

        try:
            while not self.exit_event.is_set():
                message = input()
                if not message:
                    continue
                if message.lower() == 'exit':
                    self.socket.sendto(b'exit', (self.server_address, self.server_port))
                    break

                try:
                    self.socket.sendto(message.encode(), (self.server_address, self.server_port))
                except socket.error as e:
                    print(f"\nОшибка при отправке сообщения: {e}")
                    print("Сервер может быть недоступен.")
                    self.exit_event.set()
                    break

        except KeyboardInterrupt:
            print("\nПрерывание с клавиатуры. Отключение...")
        finally:
            self.disconnect()


if __name__ == "__main__":
    client = ChatClient()
    try:
        client.run()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        client.disconnect()
