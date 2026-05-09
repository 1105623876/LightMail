from .config import APP_NAME
from .db import MailStore
from .gui.app import MailApp


def main() -> None:
    store = MailStore()
    store.initialize()
    app = MailApp(store)
    app.title(APP_NAME)
    app.mainloop()


if __name__ == "__main__":
    main()
