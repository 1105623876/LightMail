from pathlib import Path

APP_NAME = "Python 邮件客户端"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "mail_client.db"

DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_POP3_HOST = "pop.qq.com"
DEFAULT_POP3_PORT = 995
DEFAULT_USE_SSL = True
DEFAULT_FETCH_LIMIT = 20
