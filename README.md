# LightMail

LightMail 是一个用于计算机网络实践课程的软件设计项目。项目使用 Python 实现 Windows 桌面邮件客户端，支持 SMTP 发信、POP3 收信、邮件阅读、删除和本地缓存。

## 功能

- QQ 邮箱 SMTP/POP3 默认配置
- 使用 `socket` / `ssl` 手写 SMTP、POP3 协议流程
- 使用 Tkinter ttk 实现桌面图形界面
- 使用 SQLite 保存账号配置和邮件缓存
- 支持邮件编写、发送、接收、阅读、删除
- 支持 HTML 邮件正文转纯文本显示
- 支持 MIME 主题、发件人、收件人解码

## 技术栈

- Python 3.10+
- Tkinter ttk
- SQLite
- socket / ssl
- email 标准库

项目不依赖第三方 Python 包。

## 运行方式

在项目根目录执行：

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m mail_app.main
```

如果已经激活虚拟环境：

```powershell
$env:PYTHONPATH='src'
python -m mail_app.main
```

## QQ 邮箱授权码配置

程序需要填写 QQ 邮箱授权码，不是 QQ 登录密码。

获取方式：

1. 登录 QQ 邮箱网页版。
2. 进入“设置”。
3. 打开“账号”设置。
4. 找到“POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务”。
5. 开启 `POP3/SMTP服务`。
6. 按提示生成授权码。

默认服务器配置：

| 类型 | 主机 | 端口 | SSL |
| --- | --- | --- | --- |
| SMTP | `smtp.qq.com` | `465` | 是 |
| POP3 | `pop.qq.com` | `995` | 是 |

## 项目结构

```text
src/
  mail_app/
    main.py                 # 程序入口
    config.py               # 默认配置
    db.py                   # SQLite 存储层
    mime_utils.py           # MIME 生成、解析和正文清理
    protocol/
      smtp_client.py        # SMTP socket 客户端
      pop3_client.py        # POP3 socket 客户端
    gui/
      app.py                # Tkinter ttk 图形界面
```

## 本地数据

运行后会生成本地数据库：

```text
data/mail_client.db
```

该文件保存账号配置、授权码和邮件缓存，已被 `.gitignore` 忽略，不应提交到 GitHub。

## 验证

编译检查：

```powershell
.\.venv\Scripts\python.exe -m compileall src
```

GUI 创建测试：

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -c "from mail_app.db import MailStore; from mail_app.gui.app import MailApp; s=MailStore(); s.initialize(); app=MailApp(s); app.update_idletasks(); print('gui ok'); app.destroy()"
```

## 课程说明

本项目为了符合课程要求，没有使用 `smtplib`、`poplib` 等高级邮件客户端库替代协议实现。SMTP、POP3 的连接、认证、命令发送和响应读取均基于底层 socket 实现。
