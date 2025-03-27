import socket
import sys


class ChatServer:
    def __init__(self):
        self.server_ip = self.get_valid_ip()
        self.server_port = self.get_valid_port()
        self.connected_clients = {}
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            self.server_socket.bind((self.server_ip, self.server_port))
            print(f"\nСервер запущен на {self.server_ip}: {self.server_port}")
            print("Ожидание подключений\n")
        except socket.error as e:
            print(f"Ошибка привязки к {self.server_ip}:{self.server_port}: {e}")
            sys.exit(1)

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
        for client_address, (client_name, _, _) in self.connected_clients.items():
            if client_address != sender_address:
                try:
                    self.server_socket.sendto(message.encode(), client_address)
                except socket.error as e:
                    print(f"Ошибка отправки {client_name}: {e}")
                    del self.connected_clients[client_address]

    def run(self):
        while True:
            try:
                data, client_address = self.server_socket.recvfrom(1024)
                data = data.decode()

                if client_address not in self.connected_clients:
                    if data.startswith("reg:"):
                        client_name = data.split(":")[1]
                        self.connected_clients[client_address] = (client_name, client_address[0], client_address[1])
                        print(f"Подключился (-ась) {client_name} ({client_address[0]}: {client_address[1]})")
                        self.broadcast_message(f"Пользователь {client_name} вошел в чат", client_address)
                        continue

                if data.lower() == 'exit':
                    client_name = self.connected_clients[client_address][0]
                    del self.connected_clients[client_address]
                    print(f"{client_name} отключился")
                    self.broadcast_message(f"Пользователь {client_name} вышел из чата", client_address)
                    continue

                client_name = self.connected_clients[client_address][0]
                message = f"{client_name}: {data}"
                print(message)
                self.broadcast_message(message, client_address)

            except Exception as e:
                print(f"Ошибка: {e}")


if __name__ == "__main__":
    server = ChatServer()
    server.run()
