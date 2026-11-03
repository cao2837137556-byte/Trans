"""SSH transport only; normal host-key and authentication checks still apply."""
import os
import socket
import struct
import sys
import threading


def exact(sock, count):
    out = b''
    while len(out) < count:
        part = sock.recv(count - len(out))
        if not part: raise ConnectionError('SOCKS closed')
        out += part
    return out


def connect(port, target):
    sock = socket.create_connection(('127.0.0.1', int(port)), timeout=10)
    sock.sendall(b'\x05\x01\x00')
    assert exact(sock, 2) == b'\x05\x00'
    sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01' + struct.pack('!H', target))
    reply = exact(sock, 4)
    assert reply[:3] == b'\x05\x00\x00'
    exact(sock, 4 if reply[3] == 1 else 16 if reply[3] == 4 else exact(sock, 1)[0]); exact(sock, 2)
    return sock


if __name__ == '__main__':
    sock = connect(sys.argv[1], 2222); sock.settimeout(None)
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY); msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    def outgoing():
        try:
            while True:
                data = os.read(sys.stdin.fileno(), 65536)
                if not data: sock.shutdown(socket.SHUT_WR); return
                sock.sendall(data)
        except OSError: pass
    threading.Thread(target=outgoing, daemon=True).start()
    while True:
        data = sock.recv(65536)
        if not data: break
        sys.stdout.buffer.write(data); sys.stdout.buffer.flush()
