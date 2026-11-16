# this_file: examples/fixtures/timer_process/app.py
# SPDX-License-Identifier: Apache-2.0
"""A repeating QTimer and three nonblocking QProcess runs: success, error, cancel."""

import sys

from PySide2 import QtCore, QtWidgets


class Runner(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timer and processes")
        self.ticks = 0
        self.log = []
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.echo = self.launch("/bin/echo", ["pythonqtside"])
        self.missing = self.launch("/nonexistent/pythonqtside-tool", [])
        self.sleeper = self.launch("/bin/sleep", ["30"])

    def tick(self):
        self.ticks += 1

    def launch(self, program, arguments):
        process = QtCore.QProcess(self)
        process.finished.connect(
            lambda code, status, p=process, n=program: self.log.append(
                ("finished", n, code, bytes(p.readAllStandardOutput()).decode().strip())
            )
        )
        process.errorOccurred.connect(
            lambda error, n=program: self.log.append(("error", n, int(error)))
        )
        process.start(program, arguments)
        return process

    def cancel(self):
        self.sleeper.kill()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    runner = Runner()
    runner.show()
    sys.exit(app.exec_())
