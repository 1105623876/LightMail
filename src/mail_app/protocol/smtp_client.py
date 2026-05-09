from __future__ import annotations

import base64
import socket
import ssl
from dataclasses import dataclass, field


class SMTPError(RuntimeError):
    pass


@dataclass
class SMTPClient:
    host: str
    port: int
    use_ssl: bool = True
    timeout: float = 20.0
    log: list[str] = field(default_factory=list)

    def send_mail(self, username: str, auth_code: str, recipient: str, message: str) -> list[str]:
        self.log.clear()
        with self._connect() as sock:
            self._expect(sock, {220})
            self._send(sock, f"EHLO {socket.gethostname()}")
            self._expect(sock, {250})
            self._auth_login(sock, username, auth_code)
            self._send(sock, f"MAIL FROM:<{username}>")
            self._expect(sock, {250})
            self._send(sock, f"RCPT TO:<{recipient}>")
            self._expect(sock, {250, 251})
            self._send(sock, "DATA")
            self._expect(sock, {354})
            self._send_data(sock, message)
            self._expect(sock, {250})
            self._send(sock, "QUIT")
            self._expect(sock, {221})
        return self.log.copy()

    def _connect(self):
        raw_sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if not self.use_ssl:
            return raw_sock
        context = ssl.create_default_context()
        return context.wrap_socket(raw_sock, server_hostname=self.host)

    def _auth_login(self, sock, username: str, auth_code: str) -> None:
        self._send(sock, "AUTH LOGIN")
        self._expect(sock, {334})
        self._send(sock, base64.b64encode(username.encode("utf-8")).decode("ascii"))
        self._expect(sock, {334})
        self._send(sock, base64.b64encode(auth_code.encode("utf-8")).decode("ascii"))
        self._expect(sock, {235})

    def _send(self, sock, command: str) -> None:
        self.log.append(f"> {self._mask(command)}")
        sock.sendall((command + "\r\n").encode("utf-8"))

    def _send_data(self, sock, message: str) -> None:
        normalized = message.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        escaped = "\r\n".join("." + line if line.startswith(".") else line for line in lines)
        sock.sendall((escaped + "\r\n.\r\n").encode("utf-8"))
        self.log.append("> [message body]")
        self.log.append("> .")

    def _expect(self, sock, expected_codes: set[int]) -> str:
        response = self._read_response(sock)
        code = int(response[:3]) if len(response) >= 3 and response[:3].isdigit() else -1
        if code not in expected_codes:
            raise SMTPError(f"SMTP 响应异常，期望 {sorted(expected_codes)}，实际：{response}")
        return response

    def _read_response(self, sock) -> str:
        lines: list[str] = []
        while True:
            line = self._recv_line(sock)
            lines.append(line)
            self.log.append(f"< {line}")
            if len(line) < 4 or line[3] != "-":
                break
        return "\n".join(lines)

    def _recv_line(self, sock) -> str:
        data = bytearray()
        while not data.endswith(b"\n"):
            chunk = sock.recv(1)
            if not chunk:
                break
            data.extend(chunk)
        return data.decode("utf-8", errors="replace").rstrip("\r\n")

    def _mask(self, command: str) -> str:
        if command == "AUTH LOGIN":
            return command
        if self.log and self.log[-1].startswith("< 334"):
            return "[base64 credential]"
        return command
