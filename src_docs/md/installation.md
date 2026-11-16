---
this_file: src_docs/md/installation.md
---

# Installation

FontLab uses native PythonQt/Qt5 on arm64 Python 3.11. Offline Python 3.12 development and standalone Qt6 observations do not establish native support. Pythonqtside never imports or installs a second Qt binding or creates QApplication.

Installation commands are retained under [development and limits](development-and-limits.md#running-existing-applications); basic package usage is in the [overview](index.md). Use a matching Echopy package; ordinary wheel installation and native host installation are separate acceptance surfaces. The source installer remains unchanged.
