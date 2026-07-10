from __future__ import annotations
import sys
import asyncio
import logging
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from .main_window import MainWindow


def main() -> None:
    log_file = "/tmp/alexa_device_manager.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, mode="w"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    log = logging.getLogger(__name__)
    log.info("Logging to %s", log_file)

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
