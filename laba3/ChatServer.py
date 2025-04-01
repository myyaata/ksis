import socket
import sys
import signal
import time


class ChatServer:
    def __init__(self):
        self.server_ip = self.get_valid_ip()
        self.server_port = self.get_valid_port()
        self.connected_clients = {}
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = True

        # Настройка обработчиков сигналов для корректного завершения
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            self.server_socket.bind((self.server_ip, self.server_port))
            # Устанавливаем таймаут для сокета, чтобы можно было периодически проверять статус
            self.server_socket.settimeout(1.0)
            print(f"\nСервер запущен на {self.server_ip}: {self.server_port}")
            print("Ожидание подключений\n")
            print("Нажмите Ctrl+C для завершения работы сервера")
        except socket.error as e:
            print(f"Ошибка привязки к {self.server_ip}:{self.server_port}: {e}")
            sys.exit(1)

    def handle_shutdown(self, signum, frame):
        """Обработчик сигналов завершения"""
        print("\nПолучен сигнал завершения. Закрытие сервера...")
        self.shutdown()

    def shutdown(self):
        """Корректное завершение работы сервера"""
        if not self.running:
            return

        self.running = False
        # Уведомляем всех клиентов о закрытии сервера
        shutdown_message = "Сервер закрывается. Соединение будет прервано."
        for client_address, client_info in self.connected_clients.items():
            try:
                self.server_socket.sendto(shutdown_message.encode(), client_address)
            except:
                pass  # Игнорируем ошибки при завершении

        # Закрываем сокет
        try:
            self.server_socket.close()
        except:
            pass

        print("Сервер остановлен.")

    def get_valid_ip(self):
        while True:
            ip = input("Введите IP сервера (или ничего для локального хоста): ").strip()
            if not ip:
                return '127.0.0.1'
            try:
                socket.inet_aton(ip)
                return ip
            except socket.error:
                print("Некорректный IP-адрес")

    def get_valid_port(self):
        while True:
            try:
                port = int(input("Введите порт сервера (1024-65535): "))
                if 1024 <= port <= 65535:
                    return port
                print("Порт должен быть в диапазоне 1024-65535")
            except ValueError:
                print("Введите число")

    def broadcast_message(self, message, sender_address=None):
        """Отправка сообщения всем клиентам, кроме отправителя"""
        disconnected_clients = []

        for client_address, client_info in self.connected_clients.items():
            if client_address != sender_address:
                try:
                    client_name, client_ip, client_port = client_info
                    self.server_socket.sendto(message.encode(), client_address)
                except socket.error as e:
                    print(f"Ошибка отправки {client_info[0]}: {e}")
                    disconnected_clients.append(client_address)

        # Удаляем отключенных клиентов
        for client in disconnected_clients:
            if client in self.connected_clients:
                print(f"Отключен клиент {self.connected_clients[client][0]} из-за ошибки связи")
                del self.connected_clients[client]

    def run(self):
        while self.running:
            try:
                # Получаем данные с таймаутом
                data, client_address = self.server_socket.recvfrom(1024)
                data = data.decode()

                if client_address not in self.connected_clients:
                    if data.startswith("reg:"):
                        parts = data.split(":")
                        if len(parts) >= 3:
                            client_name = parts[1]
                            client_ip = parts[2]
                            # Проверяем, что предоставленный IP соответствует адресу, с которого пришло сообщение
                            if client_ip != client_address[0]:
                                self.server_socket.sendto(
                                    f"Ошибка: Указанный IP ({client_ip}) не соответствует фактическому ({client_address[0]})".encode(),
                                    client_address)
                                continue

                            self.connected_clients[client_address] = (client_name, client_ip, client_address[1])
                            print(f"Подключился (-ась) {client_name} ({client_ip}: {client_address[1]})")
                            self.broadcast_message(f"Пользователь {client_name} вошел в чат", client_address)
                        else:
                            self.server_socket.sendto("Ошибка: Неверный формат регистрации".encode(), client_address)
                        continue

                if data.lower() == 'exit':
                    if client_address in self.connected_clients:
                        client_name = self.connected_clients[client_address][0]
                        del self.connected_clients[client_address]
                        print(f"{client_name} отключился")
                        self.broadcast_message(f"Пользователь {client_name} вышел из чата", client_address)
                    continue

                if client_address in self.connected_clients:
                    client_name = self.connected_clients[client_address][0]
                    message = f"{client_name}: {data}"
                    print(message)
                    self.broadcast_message(message, client_address)

            except socket.timeout:
                # Таймаут сокета - нормальная ситуация, используем для проверки флага running
                continue
            except ConnectionResetError as e:
                print(f"Соединение сброшено: {e}")
                # Попытка переинициализировать сокет
                try:
                    self.server_socket.close()
                    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.server_socket.bind((self.server_ip, self.server_port))
                    self.server_socket.settimeout(1.0)
                    print("Сокет переинициализирован")
                except socket.error as se:
                    print(f"Невозможно восстановить сокет: {se}")
                    self.shutdown()
            except socket.error as e:
                print(f"Ошибка сокета: {e}")
                if not self.running:
                    break
            except KeyboardInterrupt:
                print("\nПрерывание с клавиатуры. Завершение работы...")
                self.shutdown()
            except Exception as e:
                print(f"Непредвиденная ошибка: {e}")
                if not self.running:
                    break


if __name__ == "__main__":
    server = ChatServer()
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
