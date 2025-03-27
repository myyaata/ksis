import socket
import sys
from threading import Thread, Event
import time


class ChatClient:
    def __init__(self):
        self.username = input("Введите ваше имя: ").strip()
        self.server_address = self.get_valid_ip()
        self.server_port = self.get_valid_port("сервера")
        self.client_port = self.get_valid_port("клиента")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.exit_event = Event()
        try:
            self.socket.bind(('', self.client_port))
            print(f"\n{self.username}, вы подключены на порту {self.client_port}")
            print("Введите сообщение (выход - 'exit'):\n")
        except socket.error as e:
            print(f"Ошибка привязки к порту {self.client_port}: {e}")
            sys.exit(1)

    def get_valid_ip(self):
        while True:
            ip = input("IP сервера: ").strip()
            parts = ip.split(".")
            if len(parts) != 4:
                print("IP должен содержать 4 октета")
                continue
            try:
                if not all(0 <= int(part) <= 255 for part in parts):
                    print("Каждый октет IP должен быть 0-255")
                    continue
                return ip
            except ValueError:
                print("Некорректный IP-адрес")

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
        while not self.exit_event.is_set():
            try:
                data, _ = self.socket.recvfrom(1024)
                print(data.decode())
            except socket.error as e:
                if not self.exit_event.is_set():
                    print(f"\nСоединение прервано: {e}")
                break

    def run(self):
        listener_thread = Thread(target=self.listen_for_messages, daemon=True)
        listener_thread.start()

        self.socket.sendto(f"reg:{self.username}".encode(), (self.server_address, self.server_port))

        try:
            while True:
                message = input()
                if not message:
                    continue
                if message.lower() == 'exit':
                    self.socket.sendto(b'exit', (self.server_address, self.server_port))
                    break
                self.socket.sendto(message.encode(), (self.server_address, self.server_port))
        finally:
            self.exit_event.set()
            time.sleep(0.1)
            self.socket.close()
            print("\nОтключение от сервера")


if __name__ == "__main__":
    client = ChatClient()
    client.run()
