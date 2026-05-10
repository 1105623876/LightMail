from __future__ import annotations

import re
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
        self.configure(bg="#f5f8fc")
        self._build_styles()
        self._build_widgets()
        self._load_last_account()

    def _build_styles(self) -> None:
        self.bg = "#f5f8fc"
        self.surface = "#ffffff"
        self.surface_muted = "#f8fbff"
        self.primary = "#2563eb"
        self.primary_dark = "#1d4ed8"
        self.primary_soft = "#dbeafe"
        self.primary_pale = "#eff6ff"
        self.primary_deep = "#1e3a8a"
        self.control_border = "#cbd8ea"
        self.button_soft = "#edf4ff"
        self.tab_soft = "#eaf2ff"
        self.text = "#0f172a"
        self.text_muted = "#475569"
        self.border = "#d8e4f2"

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=self.bg)
        self.style.configure("Card.TFrame", background=self.surface)
        self.style.configure("Header.TFrame", background=self.primary_soft)
        self.style.configure(
            "TLabelframe",
            background=self.bg,
            bordercolor=self.border,
            relief="solid",
        )
        self.style.configure(
            "TLabelframe.Label",
            background=self.bg,
            foreground=self.text,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.style.configure("TLabel", background=self.bg, foreground=self.text_muted, font=("Microsoft YaHei UI", 9))
        self.style.configure("Title.TLabel", background=self.primary_soft, foreground=self.primary_deep, font=("Microsoft YaHei UI", 19, "bold"))
        self.style.configure("Subtitle.TLabel", background=self.primary_soft, foreground=self.text_muted, font=("Microsoft YaHei UI", 9))
        self.style.configure(
            "TEntry",
            fieldbackground=self.surface_muted,
            foreground=self.text,
            padding=6,
            bordercolor=self.control_border,
            lightcolor=self.control_border,
            darkcolor=self.control_border,
        )
        self.style.configure(
            "TCheckbutton",
            background=self.bg,
            foreground=self.text_muted,
            font=("Microsoft YaHei UI", 9),
        )
        self.style.configure(
            "TButton",
            font=("Microsoft YaHei UI", 9),
            padding=(12, 8),
            background=self.button_soft,
            foreground=self.text,
            bordercolor=self.control_border,
        )
        self.style.map(
            "TButton",
            background=[("active", "#dbeafe"), ("disabled", "#eef2f7")],
            foreground=[("disabled", "#94a3b8")],
        )
        self.style.configure(
            "Accent.TButton",
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(12, 8),
            background=self.primary,
            foreground="#ffffff",
            bordercolor=self.primary,
        )
        self.style.map("Accent.TButton", background=[("active", self.primary_dark)], foreground=[("active", "#ffffff")])
        self.style.configure(
            "Treeview",
            font=("Microsoft YaHei UI", 9),
            rowheight=34,
            background=self.surface,
            fieldbackground=self.surface,
            foreground=self.text,
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Microsoft YaHei UI", 9, "bold"),
            background=self.primary_pale,
            foreground=self.text,
            borderwidth=0,
            padding=(8, 7),
        )
        self.style.map("Treeview", background=[("selected", self.primary_soft)], foreground=[("selected", self.text)])
        self.style.configure("TNotebook", background=self.bg, borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 9), padding=(14, 8), background=self.tab_soft)
        self.style.map("TNotebook.Tab", background=[("selected", self.surface), ("active", self.primary_pale)])

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Canvas(self, height=88, highlightthickness=0, bd=0, bg=self.bg)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(18, 0))
        header.bind("<Configure>", self._draw_header)

        left = ttk.Frame(self, padding=(20, 18, 16, 20))
        left.grid(row=1, column=0, sticky="nsew")
        left.columnconfigure(0, minsize=352)
        left.rowconfigure(1, weight=1)
        right = ttk.Frame(self, padding=(0, 18, 20, 20))
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
        canvas.create_rectangle(0, 0, width, 88, fill=self.primary_soft, outline="")
        canvas.create_rectangle(0, 0, width, 88, outline="#bfdbfe", width=1)
        canvas.create_oval(width - 210, -92, width + 58, 172, fill="#bfdbfe", outline="")
        canvas.create_oval(width - 324, 30, width - 218, 136, fill="#93c5fd", outline="")
        canvas.create_text(30, 27, anchor="w", text="LightMail", fill="#1e3a8a", font=("Microsoft YaHei UI", 21, "bold"))
        canvas.create_text(32, 58, anchor="w", text="基于 socket 的 SMTP / POP3 课程邮件客户端", fill=self.text_muted, font=("Microsoft YaHei UI", 9))
        canvas.create_text(width - 30, 45, anchor="e", text="Socket · SMTP · POP3 · SQLite", fill=self.primary_dark, font=("Consolas", 10, "bold"))

    def _build_account_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="账号配置", padding=(16, 14, 16, 16))
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
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(frame, textvariable=var, width=28, show="*" if secret else "")
            entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(0, 2))

        ttk.Checkbutton(frame, text="使用 SSL", variable=self.use_ssl_var).grid(row=6, column=1, sticky="w", pady=(6, 4))
        ttk.Button(frame, text="保存账号", command=self.save_account, style="Accent.TButton").grid(row=7, column=1, sticky="ew", pady=(14, 0), padx=(0, 2))

    def _build_actions_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="快捷操作", padding=(12, 12, 12, 14))
        frame.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(frame, highlightthickness=0, bd=0, bg=self.bg)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        content = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

        content.columnconfigure(0, weight=1, minsize=304)
        self.fetch_button = ttk.Button(content, text="收取最近邮件", command=self.fetch_messages, style="Accent.TButton")
        self.fetch_button.grid(row=0, column=0, sticky="ew", pady=6)
        self.compose_button = ttk.Button(content, text="写邮件", command=self.open_compose_window)
        self.compose_button.grid(row=1, column=0, sticky="ew", pady=6)
        self.delete_button = ttk.Button(content, text="删除选中邮件", command=self.delete_selected_message)
        self.delete_button.grid(row=2, column=0, sticky="ew", pady=6)
        self.reparse_button = ttk.Button(content, text="刷新本地解析", command=self.reparse_cached_messages)
        self.reparse_button.grid(row=3, column=0, sticky="ew", pady=6)
        self.clear_cache_button = ttk.Button(content, text="清空本地缓存", command=self.clear_local_cache)
        self.clear_cache_button.grid(row=4, column=0, sticky="ew", pady=6)
        self.status_var = tk.StringVar(value="请先保存账号配置。")
        ttk.Label(content, textvariable=self.status_var, wraplength=304).grid(row=5, column=0, sticky="ew", pady=(14, 0))

    def _build_inbox_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="收件箱", padding=(12, 12, 12, 10))
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("subject", "sender", "date")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("subject", text="主题")
        self.tree.heading("sender", text="发件人")
        self.tree.heading("date", text="日期")
        self.tree.column("subject", width=460, minwidth=260)
        self.tree.column("sender", width=260, minwidth=180)
        self.tree.column("date", width=210, minwidth=150)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.show_selected_message)

        y_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

    def _build_tabs(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
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
        frame = ttk.LabelFrame(parent, text="邮件详情", padding=(12, 12, 12, 10))
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
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 10))
            entry = ttk.Entry(frame, textvariable=var, state="readonly")
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            self.detail_entries.append(entry)

        self.body_text = tk.Text(
            frame,
            height=10,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            relief="flat",
            padx=14,
            pady=14,
            bg=self.surface,
            fg=self.text,
            insertbackground=self.primary,
            selectbackground=self.primary_soft,
            selectforeground=self.text,
        )
        self.body_text.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        body_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.body_text.yview)
        body_scrollbar.grid(row=4, column=2, sticky="ns", pady=(10, 0))
        self.body_text.tag_configure("md_h1", font=("Microsoft YaHei UI", 15, "bold"), foreground="#1e3a8a", spacing1=8, spacing3=6)
        self.body_text.tag_configure("md_h2", font=("Microsoft YaHei UI", 13, "bold"), foreground=self.primary_dark, spacing1=7, spacing3=5)
        self.body_text.tag_configure("md_h3", font=("Microsoft YaHei UI", 11, "bold"), foreground=self.primary, spacing1=6, spacing3=4)
        self.body_text.tag_configure("md_quote", foreground=self.text_muted, lmargin1=16, lmargin2=16)
        self.body_text.tag_configure("md_code", font=("Consolas", 10), background="#f1f5f9", foreground=self.text)
        self.body_text.configure(state="disabled", yscrollcommand=body_scrollbar.set)

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        frame = ttk.LabelFrame(parent, text="SMTP / POP3 协议日志", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        self.log_list = tk.Listbox(
            frame,
            width=28,
            activestyle="dotbox",
            font=("Consolas", 9),
            relief="flat",
            bg=self.surface,
            fg=self.text,
            selectbackground=self.primary_soft,
            selectforeground=self.text,
            highlightthickness=1,
            highlightbackground=self.border,
        )
        self.log_list.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.log_list.bind("<<ListboxSelect>>", self.show_selected_log)

        self.log_text = tk.Text(
            frame,
            wrap="none",
            font=("Consolas", 9),
            relief="flat",
            padx=12,
            pady=12,
            bg="#0b1220",
            fg="#dbeafe",
            insertbackground="#93c5fd",
            selectbackground="#1e3a8a",
            selectforeground="#ffffff",
        )
        self.log_text.grid(row=0, column=1, sticky="nsew")
        self.log_text.configure(state="disabled")

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
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
            parsed["uidl"] = str(raw.get("uidl", ""))
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
        self._set_body_text(message.body or message.raw_content)

    def _set_body_text(self, text: str) -> None:
        self.body_text.configure(state="normal")
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", text)
        self._apply_markdown_tags(text)
        self.body_text.configure(state="disabled")

    def _apply_markdown_tags(self, text: str) -> None:
        line_start = "1.0"
        in_code_block = False
        code_block_start = ""
        for line in text.splitlines():
            line_end = f"{line_start} lineend"
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_block_start = line_start
                else:
                    self.body_text.tag_add("md_code", code_block_start, line_end)
                    in_code_block = False
            elif in_code_block:
                pass
            else:
                heading = re.match(r"^(#{1,3})\s+(.+)", line)
                if heading:
                    tag = {1: "md_h1", 2: "md_h2", 3: "md_h3"}[len(heading.group(1))]
                    self.body_text.tag_add(tag, line_start, line_end)
                elif line.startswith(">"):
                    self.body_text.tag_add("md_quote", line_start, line_end)
                elif line.startswith("    ") or line.startswith("`"):
                    self.body_text.tag_add("md_code", line_start, line_end)
            line_start = self.body_text.index(f"{line_start} + 1 line")
        if in_code_block:
            self.body_text.tag_add("md_code", code_block_start, "end")

    def _clear_detail(self) -> None:
        self.detail_subject.set("")
        self.detail_from.set("")
        self.detail_to.set("")
        self.detail_date.set("")
        self._set_body_text("")

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
        window.configure(bg=self.bg)

        to_var = tk.StringVar()
        subject_var = tk.StringVar()
        frame = ttk.Frame(window, padding=(20, 18, 20, 20))
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)

        ttk.Label(frame, text="收件人").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=to_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(frame, text="主题").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=subject_var).grid(row=1, column=1, sticky="ew", pady=5)
        body = tk.Text(
            frame,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            padx=14,
            pady=14,
            relief="flat",
            bg=self.surface,
            fg=self.text,
            insertbackground=self.primary,
            selectbackground=self.primary_soft,
            selectforeground=self.text,
        )
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
            self.log_list.itemconfig("end", foreground=self.text)
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
