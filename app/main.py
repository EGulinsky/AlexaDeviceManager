from __future__ import annotations
import sys
import asyncio
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from .main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AlexaDeviceManager")
    app.setOrganizationName("AlexaDeviceManager")

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.start()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
