import socket
import struct
import time
import sys

ICMP_ECHO_REQUEST = 8
TIME_EXCEEDED = 11
HOST_UNREACHABLE = 3


def compute_checksum(data):
    total = 0
    count = (len(data) // 2) * 2
    i = 0

    while i < count:
        value = data[i + 1] * 256 + data[i]
        total += value
        total &= 0xffffffff
        i += 2

    if i < len(data):
        total += data[-1]
        total &= 0xffffffff

    total = (total >> 16) + (total & 0xffff)
    total += (total >> 16)
    result = ~total & 0xffff
    return (result >> 8) | ((result << 8) & 0xff00)


def generate_icmp_packet(identifier, sequence_number):

    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, identifier, sequence_number)
    payload = struct.pack("d", time.time())
    checksum_value = compute_checksum(header + payload)
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, checksum_value, identifier, sequence_number)
    return header + payload


def perform_traceroute(destination, max_hops=30, timeout_duration=2, packets_per_hop=3, max_timeout_count=10):
    try:
        destination_ip = socket.gethostbyname(destination)
    except socket.gaierror:
        print(f"Ошибка: не удалось разрешить имя хоста {destination}")
        return

    print(f"traceroute to {destination} ({destination_ip}), {max_hops} hops max, timeout {timeout_duration * 1000} ms\n")

    try:
        response_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        response_socket.settimeout(timeout_duration)
    except PermissionError:
        print("Ошибка: запустите программу с правами администратора (root)")
        return
    except Exception as error:
        print(f"Ошибка при создании сокетов: {error}")
        return

    packet_id = id(destination_ip) & 0xffff
    sequence_number = 0
    consecutive_timeout_counter = 0

    try:
        for ttl in range(1, max_hops + 1):
            try:
                send_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
            except Exception as error:
                print(f"Ошибка при создании сокета для отправки: {error}")
                break

            response_times = []
            visited_ips = set()  # Множество для хранения уникальных IP-адресов
            timeouts_for_hop = 0

            for _ in range(packets_per_hop):
                sequence_number += 1
                try:
                    send_time = time.time()
                    icmp_packet = generate_icmp_packet(packet_id, sequence_number)
                    send_socket.sendto(icmp_packet, (destination_ip, 0))

                    data, addr = response_socket.recvfrom(1024)
                    receive_time = time.time()
                    elapsed_time = (receive_time - send_time) * 1000

                    icmp_header = data[20:28]
                    icmp_type, _, _, _, _ = struct.unpack("!BBHHH", icmp_header)

                    if icmp_type == TIME_EXCEEDED:
                        visited_ips.add(addr[0])
                        response_times.append(f"{elapsed_time:.2f} ms")
                    elif icmp_type == HOST_UNREACHABLE:
                        visited_ips.add(addr[0])
                        response_times.append(f"{elapsed_time:.2f} ms")
                        if addr[0] == destination_ip:
                            print(f"{ttl:<4} {addr[0]:<15} {' '.join(response_times)} (Хост недоступен!)")
                            send_socket.close()
                            response_socket.close()
                            return
                    else:
                        response_times.append("*")

                    if icmp_type == 0 and addr[0] == destination_ip:
                        print(f"{ttl:<4} {addr[0]:<15} {' '.join(response_times)} ")
                        send_socket.close()
                        response_socket.close()
                        return

                except socket.timeout:
                    response_times.append("*")
                    timeouts_for_hop += 1
                except Exception as error:
                    print(f"Ошибка на хопе {ttl}: {error}")
                    response_times.append("*")

            if timeouts_for_hop == packets_per_hop:
                consecutive_timeout_counter += 1
            else:
                consecutive_timeout_counter = 0

            if consecutive_timeout_counter >= max_timeout_count:
                print("Превышено количество подряд идущих тайм-аутов. Завершение трассировки.")
                break

            ip_output = ' '.join(visited_ips) if visited_ips else "*"
            print(f"{ttl:<4} {ip_output:<15} {' '.join(response_times)}")
            send_socket.close()

    except KeyboardInterrupt:
        print("\nТрассировка прервана пользователем.")

    print("Цель не достигнута за максимальное количество хопов.")
    response_socket.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command.lower() == "mytraceroute":
            if len(sys.argv) > 2:
                destination = sys.argv[2]
            else:
                print("Ошибка: не указан адрес для трассировки.")
                sys.exit(1)
        else:
            print("Ошибка: команда не распознана.")
            sys.exit(1)
    else:
        user_input = input("Введите команду и адрес (например, mytraceroute google.com): ")
        parts = user_input.split()
        if len(parts) == 2 and parts[0].lower() == "mytraceroute":
            destination = parts[1]
        else:
            print("Ошибка: введена некорректная команда.")
            sys.exit(1)

    perform_traceroute(destination)
