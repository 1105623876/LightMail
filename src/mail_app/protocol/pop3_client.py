from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field


class POP3Error(RuntimeError):
    pass


@dataclass
class POP3Client:
    host: str
    port: int
    use_ssl: bool = True
    timeout: float = 20.0
    log: list[str] = field(default_factory=list)

    def fetch_recent(self, username: str, auth_code: str, limit: int = 20) -> list[dict[str, int | str]]:
        self.log.clear()
        messages: list[dict[str, int | str]] = []
        with self._connect() as sock:
            self._expect_ok(sock)
            self._login(sock, username, auth_code)
            count, _ = self.stat(sock)
            start = max(1, count - limit + 1)
            for number in range(count, start - 1, -1):
                raw_content = self.retrieve(sock, number)
                messages.append({"pop3_number": number, "raw_content": raw_content})
            self._send(sock, "QUIT")
            self._expect_ok(sock)
        return messages

    def delete_message(self, username: str, auth_code: str, pop3_number: int) -> list[str]:
        self.log.clear()
        with self._connect() as sock:
            self._expect_ok(sock)
            self._login(sock, username, auth_code)
            self._send(sock, f"DELE {pop3_number}")
            self._expect_ok(sock)
            self._send(sock, "QUIT")
            self._expect_ok(sock)
        return self.log.copy()

    def stat(self, sock) -> tuple[int, int]:
        self._send(sock, "STAT")
        response = self._expect_ok(sock)
        parts = response.split()
        return int(parts[1]), int(parts[2])

    def retrieve(self, sock, number: int) -> str:
        self._send(sock, f"RETR {number}")
        self._expect_ok(sock)
        lines: list[str] = []
        while True:
            line = self._recv_line(sock)
            if line == ".":
                break
            if line.startswith(".."):
                line = line[1:]
            lines.append(line)
        self.log.append(f"< [message {number} body, {len(lines)} lines]")
        return "\r\n".join(lines)

    def _connect(self):
        raw_sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if not self.use_ssl:
            return raw_sock
        context = ssl.create_default_context()
        return context.wrap_socket(raw_sock, server_hostname=self.host)

    def _login(self, sock, username: str, auth_code: str) -> None:
        self._send(sock, f"USER {username}")
        self._expect_ok(sock)
        self._send(sock, f"PASS {auth_code}", mask=True)
        self._expect_ok(sock)

    def _send(self, sock, command: str, mask: bool = False) -> None:
        self.log.append(f"> {'PASS [auth code]' if mask else command}")
        sock.sendall((command + "\r\n").encode("utf-8"))

    def _expect_ok(self, sock) -> str:
        response = self._recv_line(sock)
        self.log.append(f"< {response}")
        if not response.startswith("+OK"):
            raise POP3Error(f"POP3 响应异常：{response}")
        return response

    def _recv_line(self, sock) -> str:
        data = bytearray()
        while not data.endswith(b"\n"):
            chunk = sock.recv(1)
            if not chunk:
                break
            data.extend(chunk)
        return data.decode("utf-8", errors="replace").rstrip("\r\n")
