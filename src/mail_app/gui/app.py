from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..config import (
    DEFAULT_FETCH_LIMIT,
    DEFAULT_POP3_HOST,
    DEFAULT_POP3_PORT,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_USE_SSL,
)
from ..db import Account, MailStore, MessageSummary, ProtocolLog
from ..mime_utils import build_message, parse_message
from ..protocol.pop3_client import POP3Client
from ..protocol.smtp_client import SMTPClient



class MailApp(tk.Tk):
    def __init__(self, store: MailStore) -> None:
        super().__init__()
        self.store = store
        self.current_account: Account | None = None
        self.messages: dict[str, MessageSummary] = {}
        self.protocol_logs: dict[str, ProtocolLog] = {}
        self.geometry("1240x800")
        self.minsize(1040, 680)
        self.configure(bg="#eef3f8")
        self._build_styles()
        self._build_widgets()
        self._load_last_account()

    def _build_styles(self) -> None:
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#eef3f8")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("Header.TFrame", background="#dbeafe")
        self.style.configure("TLabelframe", background="#eef3f8", bordercolor="#d8e1ec", relief="solid")
        self.style.configure("TLabelframe.Label", background="#eef3f8", foreground="#1f2937", font=("Microsoft YaHei UI", 10, "bold"))
        self.style.configure("TLabel", background="#eef3f8", foreground="#374151", font=("Microsoft YaHei UI", 9))
        self.style.configure("Title.TLabel", background="#dbeafe", foreground="#1e3a8a", font=("Microsoft YaHei UI", 18, "bold"))
        self.style.configure("Subtitle.TLabel", background="#dbeafe", foreground="#475569", font=("Microsoft YaHei UI", 9))
        self.style.configure("TEntry", fieldbackground="#f8fafc", foreground="#111827", padding=5, bordercolor="#cbd5e1", lightcolor="#cbd5e1", darkcolor="#cbd5e1")
        self.style.configure("TButton", font=("Microsoft YaHei UI", 9), padding=(12, 8), background="#e6eef8", foreground="#1f2937", bordercolor="#cbd5e1")
        self.style.map("TButton", background=[("active", "#d8e8fb"), ("disabled", "#eef2f7")], foreground=[("disabled", "#94a3b8")])
        self.style.configure("Accent.TButton", font=("Microsoft YaHei UI", 9, "bold"), padding=(10, 7), background="#2563eb", foreground="#ffffff")
        self.style.map("Accent.TButton", background=[("active", "#1d4ed8")], foreground=[("active", "#ffffff")])
        self.style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=32, background="#ffffff", fieldbackground="#ffffff", foreground="#1f2937", borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#eff6ff", foreground="#1f2937", borderwidth=0)
        self.style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#111827")])
        self.style.configure("TNotebook", background="#eef3f8", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 9), padding=(12, 7))

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Canvas(self, height=86, highlightthickness=0, bd=0, bg="#eef3f8")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 0))
        header.bind("<Configure>", self._draw_header)

        left = ttk.Frame(self, padding=18)
        left.grid(row=1, column=0, sticky="ns")
        left.columnconfigure(0, minsize=340)
        right = ttk.Frame(self, padding=(0, 18, 18, 18))
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_account_panel(left)
        self._build_actions_panel(left)
        self._build_inbox_panel(right)
        self._build_tabs(right)

    def _draw_header(self, event) -> None:
        canvas = event.widget
        width = event.width
        canvas.delete("all")
        canvas.create_polygon(20, 0, width - 20, 0, width, 86, 0, 86, fill="#dbeafe", outline="")
        canvas.create_oval(width - 180, -80, width + 60, 160, fill="#bfdbfe", outline="")
        canvas.create_oval(width - 290, 24, width - 190, 124, fill="#93c5fd", outline="")
        canvas.create_text(28, 26, anchor="w", text="LightMail", fill="#1e3a8a", font=("Microsoft YaHei UI", 20, "bold"))
        canvas.create_text(30, 57, anchor="w", text="基于 socket 的 SMTP / POP3 课程邮件客户端", fill="#475569", font=("Microsoft YaHei UI", 9))
        canvas.create_text(width - 28, 44, anchor="e", text="Socket · SMTP · POP3 · SQLite", fill="#1d4ed8", font=("Consolas", 10, "bold"))

    def _build_account_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="账号配置", padding=16)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, minsize=82)
        frame.columnconfigure(1, weight=1)

        self.email_var = tk.StringVar()
        self.auth_code_var = tk.StringVar()
        self.smtp_host_var = tk.StringVar(value=DEFAULT_SMTP_HOST)
        self.smtp_port_var = tk.StringVar(value=str(DEFAULT_SMTP_PORT))
        self.pop3_host_var = tk.StringVar(value=DEFAULT_POP3_HOST)
        self.pop3_port_var = tk.StringVar(value=str(DEFAULT_POP3_PORT))
        self.use_ssl_var = tk.BooleanVar(value=DEFAULT_USE_SSL)

        fields = [
            ("邮箱", self.email_var, False),
            ("授权码", self.auth_code_var, True),
            ("SMTP 主机", self.smtp_host_var, False),
            ("SMTP 端口", self.smtp_port_var, False),
            ("POP3 主机", self.pop3_host_var, False),
            ("POP3 端口", self.pop3_port_var, False),
        ]
        for row, (label, var, secret) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            entry = ttk.Entry(frame, textvariable=var, width=26, show="*" if secret else "")
            entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(0, 4))

        ttk.Checkbutton(frame, text="使用 SSL", variable=self.use_ssl_var).grid(row=6, column=1, sticky="w", pady=4)
        ttk.Button(frame, text="保存账号", command=self.save_account, style="Accent.TButton").grid(row=7, column=1, sticky="ew", pady=(12, 0), padx=(0, 4))

    def _build_actions_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="快捷操作", padding=16)
        frame.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        frame.columnconfigure(0, weight=1, minsize=300)
        self.fetch_button = ttk.Button(frame, text="收取最近邮件", command=self.fetch_messages, style="Accent.TButton")
        self.fetch_button.grid(row=0, column=0, sticky="ew", pady=5)
        self.compose_button = ttk.Button(frame, text="写邮件", command=self.open_compose_window)
        self.compose_button.grid(row=1, column=0, sticky="ew", pady=5)
        self.delete_button = ttk.Button(frame, text="删除选中邮件", command=self.delete_selected_message)
        self.delete_button.grid(row=2, column=0, sticky="ew", pady=5)
        self.reparse_button = ttk.Button(frame, text="刷新本地解析", command=self.reparse_cached_messages)
        self.reparse_button.grid(row=3, column=0, sticky="ew", pady=5)
        self.clear_cache_button = ttk.Button(frame, text="清空本地缓存", command=self.clear_local_cache)
        self.clear_cache_button.grid(row=4, column=0, sticky="ew", pady=5)
        self.status_var = tk.StringVar(value="请先保存账号配置。")
        ttk.Label(frame, textvariable=self.status_var, wraplength=300).grid(row=5, column=0, sticky="ew", pady=(12, 0))

    def _build_inbox_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="收件箱", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("subject", "sender", "date")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("subject", text="主题")
        self.tree.heading("sender", text="发件人")
        self.tree.heading("date", text="日期")
        self.tree.column("subject", width=430)
        self.tree.column("sender", width=260)
        self.tree.column("date", width=210)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.show_selected_message)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _build_tabs(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        detail_tab = ttk.Frame(notebook, padding=0)
        detail_tab.rowconfigure(0, weight=1)
        detail_tab.columnconfigure(0, weight=1)
        log_tab = ttk.Frame(notebook, padding=0)
        log_tab.rowconfigure(0, weight=1)
        log_tab.columnconfigure(0, weight=1)
        notebook.add(detail_tab, text="邮件详情")
        notebook.add(log_tab, text="协议日志")
        self._build_detail_panel(detail_tab)
        self._build_log_panel(log_tab)

    def _build_detail_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        frame = ttk.LabelFrame(parent, text="邮件详情", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(4, weight=1)
        frame.columnconfigure(1, weight=1)

        self.detail_subject = tk.StringVar()
        self.detail_from = tk.StringVar()
        self.detail_to = tk.StringVar()
        self.detail_date = tk.StringVar()
        self.detail_entries: list[ttk.Entry] = []
        rows = [("主题", self.detail_subject), ("发件人", self.detail_from), ("收件人", self.detail_to), ("日期", self.detail_date)]
        for row, (label, var) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
            entry = ttk.Entry(frame, textvariable=var, state="readonly")
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.detail_entries.append(entry)

        self.body_text = tk.Text(frame, height=10, wrap="word", font=("Microsoft YaHei UI", 10), relief="flat", padx=12, pady=12, bg="#ffffff", fg="#1f2937", insertbackground="#2563eb")
        self.body_text.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        body_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.body_text.yview)
        body_scrollbar.grid(row=4, column=2, sticky="ns", pady=(10, 0))
        self.body_text.configure(state="disabled", yscrollcommand=body_scrollbar.set)

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        frame = ttk.LabelFrame(parent, text="SMTP / POP3 协议日志", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        self.log_list = tk.Listbox(frame, width=26, activestyle="dotbox", font=("Consolas", 9), relief="flat", bg="#ffffff", fg="#1f2937")
        self.log_list.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.log_list.bind("<<ListboxSelect>>", self.show_selected_log)

        self.log_text = tk.Text(frame, wrap="none", font=("Consolas", 9), relief="flat", padx=10, pady=10, bg="#0f172a", fg="#dbeafe", insertbackground="#93c5fd")
        self.log_text.grid(row=0, column=1, sticky="nsew")
        self.log_text.configure(state="disabled")

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="刷新日志", command=self.refresh_protocol_logs).grid(row=0, column=0, sticky="w")
        ttk.Button(buttons, text="导出当前日志", command=self.export_selected_log, style="Accent.TButton").grid(row=0, column=1, sticky="e")

    def _load_last_account(self) -> None:
        account = self.store.get_last_account()
        if not account:
            return
        self._fill_account(account)
        self.current_account = account
        self.refresh_message_list()
        self.refresh_protocol_logs()
        self.status_var.set(f"已加载账号：{account.email}")

    def _fill_account(self, account: Account) -> None:
        self.email_var.set(account.email)
        self.auth_code_var.set(account.auth_code)
        self.smtp_host_var.set(account.smtp_host)
        self.smtp_port_var.set(str(account.smtp_port))
        self.pop3_host_var.set(account.pop3_host)
        self.pop3_port_var.set(str(account.pop3_port))
        self.use_ssl_var.set(account.use_ssl)

    def read_account_form(self) -> Account:
        email = self.email_var.get().strip()
        auth_code = self.auth_code_var.get().strip()
        if not email or not auth_code:
            raise ValueError("邮箱和授权码不能为空。")
        return Account(
            email=email,
            auth_code=auth_code,
            smtp_host=self.smtp_host_var.get().strip() or DEFAULT_SMTP_HOST,
            smtp_port=int(self.smtp_port_var.get().strip()),
            pop3_host=self.pop3_host_var.get().strip() or DEFAULT_POP3_HOST,
            pop3_port=int(self.pop3_port_var.get().strip()),
            use_ssl=self.use_ssl_var.get(),
        )

    def save_account(self) -> None:
        try:
            account = self.read_account_form()
        except Exception as exc:
            messagebox.showerror("账号配置错误", str(exc))
            return
        self.store.save_account(account)
        self.current_account = account
        self.refresh_message_list()
        self.refresh_protocol_logs()
        self.status_var.set(f"账号已保存：{account.email}")

    def fetch_messages(self) -> None:
        account = self._ensure_account()
        if not account:
            return
        self._run_background("正在收取邮件...", lambda: self._fetch_messages_worker(account))

    def _fetch_messages_worker(self, account: Account) -> str:
        client = POP3Client(account.pop3_host, account.pop3_port, account.use_ssl)
        raw_messages = client.fetch_recent(account.email, account.auth_code, DEFAULT_FETCH_LIMIT)
        parsed_messages = []
        for raw in raw_messages:
            parsed = parse_message(str(raw["raw_content"]))
            parsed["pop3_number"] = int(raw["pop3_number"])
            parsed_messages.append(parsed)
        cached = self.store.cache_messages(account.email, parsed_messages)
        self.store.add_protocol_log(account.email, "POP3 收取邮件", client.log)
        self.after(0, self.refresh_message_list)
        self.after(0, self.refresh_protocol_logs)
        return f"收取完成：获取 {len(raw_messages)} 封，更新缓存 {cached} 封。"

    def refresh_message_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.messages.clear()
        account = self.current_account
        if not account:
            return
        for message in self.store.list_messages(account.email):
            item_id = str(message.id)
            self.messages[item_id] = message
            self.tree.insert("", "end", iid=item_id, values=(message.subject, message.sender, message.sent_at))

    def reparse_cached_messages(self) -> None:
        account = self._ensure_account()
        if not account:
            return
        count = 0
        for message in self.store.list_messages(account.email):
            parsed = parse_message(message.raw_content)
            self.store.update_message_parse(message.id, parsed)
            count += 1
        self.refresh_message_list()
        self.status_var.set(f"已刷新本地解析：{count} 封邮件。")

    def clear_local_cache(self) -> None:
        account = self._ensure_account()
        if not account:
            return
        if not messagebox.askyesno("确认清空", "确定清空当前账号的本地邮件缓存？远程邮箱不会受影响。"):
            return
        count = self.store.clear_messages(account.email)
        self.refresh_message_list()
        self._clear_detail()
        self.status_var.set(f"已清空本地缓存：{count} 封邮件。")

    def show_selected_message(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        message = self.messages.get(selection[0])
        if not message:
            return
        self.detail_subject.set(message.subject)
        self.detail_from.set(message.sender)
        self.detail_to.set(message.recipient)
        self.detail_date.set(message.sent_at)
        self.body_text.configure(state="normal")
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", message.body or message.raw_content)
        self.body_text.configure(state="disabled")

    def _clear_detail(self) -> None:
        self.detail_subject.set("")
        self.detail_from.set("")
        self.detail_to.set("")
        self.detail_date.set("")
        self.body_text.configure(state="normal")
        self.body_text.delete("1.0", "end")
        self.body_text.configure(state="disabled")

    def delete_selected_message(self) -> None:
        account = self._ensure_account()
        if not account:
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选中一封邮件。")
            return
        message = self.messages[selection[0]]
        if not messagebox.askyesno("确认删除", f"确定删除邮件：{message.subject}？"):
            return
        self._run_background("正在删除邮件...", lambda: self._delete_message_worker(account, message))

    def _delete_message_worker(self, account: Account, message: MessageSummary) -> str:
        client = POP3Client(account.pop3_host, account.pop3_port, account.use_ssl)
        client.delete_message(account.email, account.auth_code, message.pop3_number)
        self.store.add_protocol_log(account.email, "POP3 删除邮件", client.log)
        self.store.mark_deleted(message.id)
        self.after(0, self.refresh_message_list)
        self.after(0, self.refresh_protocol_logs)
        return "邮件已删除。"

    def open_compose_window(self) -> None:
        account = self._ensure_account()
        if not account:
            return
        window = tk.Toplevel(self)
        window.title("写邮件")
        window.geometry("760x600")
        window.transient(self)

        to_var = tk.StringVar()
        subject_var = tk.StringVar()
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="收件人").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=to_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(frame, text="主题").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=subject_var).grid(row=1, column=1, sticky="ew", pady=5)
        body = tk.Text(frame, wrap="word", font=("Microsoft YaHei UI", 10), padx=12, pady=12, relief="flat", bg="#ffffff", fg="#1f2937", insertbackground="#2563eb")
        body.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(8, 10))

        def send() -> None:
            recipient = to_var.get().strip()
            subject = subject_var.get().strip()
            content = body.get("1.0", "end").strip()
            if not recipient or not subject or not content:
                messagebox.showerror("发送失败", "收件人、主题和正文不能为空。", parent=window)
                return
            window.destroy()
            self._run_background("正在发送邮件...", lambda: self._send_message_worker(account, recipient, subject, content))

        ttk.Button(frame, text="发送", command=send, style="Accent.TButton").grid(row=3, column=1, sticky="e")

    def _send_message_worker(self, account: Account, recipient: str, subject: str, body: str) -> str:
        message = build_message(account.email, recipient, subject, body)
        client = SMTPClient(account.smtp_host, account.smtp_port, account.use_ssl)
        client.send_mail(account.email, account.auth_code, recipient, message)
        self.store.add_protocol_log(account.email, "SMTP 发送邮件", client.log)
        self.after(0, self.refresh_protocol_logs)
        return "邮件发送成功。"

    def refresh_protocol_logs(self) -> None:
        self.log_list.delete(0, "end")
        self.protocol_logs.clear()
        account = self.current_account
        if not account:
            return
        for log in self.store.list_protocol_logs(account.email):
            key = str(log.id)
            self.protocol_logs[key] = log
            self.log_list.insert("end", f"{log.created_at}  {log.action}")
            self.log_list.itemconfig("end", foreground="#1f2937")
            self.log_list.selection_clear(0, "end")

    def show_selected_log(self, _event=None) -> None:
        selection = self.log_list.curselection()
        if not selection:
            return
        logs = list(self.protocol_logs.values())
        if selection[0] >= len(logs):
            return
        log = logs[selection[0]]
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", f"[{log.created_at}] {log.action}\n\n{log.content}")
        self.log_text.configure(state="disabled")

    def export_selected_log(self) -> None:
        selection = self.log_list.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一条协议日志。")
            return
        logs = list(self.protocol_logs.values())
        log = logs[selection[0]]
        path = filedialog.asksaveasfilename(
            title="导出协议日志",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"protocol-log-{log.id}.txt",
        )
        if not path:
            return
        Path(path).write_text(f"[{log.created_at}] {log.action}\n\n{log.content}", encoding="utf-8")
        self.status_var.set(f"协议日志已导出：{path}")

    def _ensure_account(self) -> Account | None:
        try:
            account = self.read_account_form()
        except Exception as exc:
            messagebox.showerror("账号配置错误", str(exc))
            return None
        self.store.save_account(account)
        self.current_account = account
        return account

    def _run_background(self, status: str, task) -> None:
        self.status_var.set(status)
        self._set_actions_state("disabled")

        def worker() -> None:
            try:
                result = task()
            except Exception as exc:
                self.after(0, lambda error=exc: self._show_error(error))
            else:
                self.after(0, lambda text=result: self.status_var.set(text))
            finally:
                self.after(0, lambda: self._set_actions_state("normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _set_actions_state(self, state: str) -> None:
        self.fetch_button.configure(state=state)
        self.compose_button.configure(state=state)
        self.delete_button.configure(state=state)
        self.reparse_button.configure(state=state)
        self.clear_cache_button.configure(state=state)

    def _show_error(self, exc: Exception) -> None:
        self.status_var.set("操作失败。")
        messagebox.showerror("操作失败", str(exc))
