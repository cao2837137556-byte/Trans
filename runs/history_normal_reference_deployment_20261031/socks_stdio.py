"""OpenSSH ProxyCommand through the user's existing VS Code SOCKS tunnel."""
import argparse
import socket
import struct
import sys
import threading


def receive(sock, count):
    data = b''
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise ConnectionError('SOCKS_CLOSED')
        data += part
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socks-port', type=int, required=True)
    parser.add_argument('--destination-port', type=int, default=2222)
    args = parser.parse_args()
    if not all(0 < p < 65536 for p in (args.socks_port, args.destination_port)):
        raise ValueError('INVALID_PORT')
    sock = socket.create_connection(('127.0.0.1', args.socks_port), timeout=15)
    sock.sendall(b'\x05\x01\x00')
    if receive(sock, 2) != b'\x05\x00':
        raise ConnectionError('SOCKS_NEGOTIATION')
    sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01' + struct.pack('!H', args.destination_port))
    reply = receive(sock, 4)
    if reply[:3] != b'\x05\x00\x00':
        raise ConnectionError('SOCKS_DESTINATION_REFUSED')
    length = 4 if reply[3] == 1 else 16 if reply[3] == 4 else receive(sock, 1)[0]
    receive(sock, length)
    receive(sock, 2)
    sock.settimeout(None)

    def send():
        try:
            while True:
                block = sys.stdin.buffer.read1(65536)
                if not block:
                    sock.shutdown(socket.SHUT_WR)
                    return
                sock.sendall(block)
        except OSError:
            pass

    threading.Thread(target=send, daemon=True).start()
    try:
        while True:
            block = sock.recv(65536)
            if not block:
                break
            sys.stdout.buffer.write(block)
            sys.stdout.buffer.flush()
    finally:
        sock.close()


if __name__ == '__main__':
    main()
