---
this_file: src_docs/md/index.md
---

# Pythonqtside


`pythonqtside` supplies inventory-based Qt5 namespace routing for FontLab PythonQt.
What runs unchanged, what is adapted and what is not supported is listed in the
[compatibility guide](pythonqt-compatibility.md); completed work is in
[CHANGELOG.md](https://github.com/fontlabcom/pythonqtside/blob/a09947183354ddb1475a903cec744e8545505ce6/CHANGELOG.md). This package never imports or installs a second Qt
binding or creates a QApplication.

```python
from pythonqtside import QtCore, QtGui, QtWidgets
widget = QtWidgets.QWidget()  # Inside FontLab: the original native QWidget.
```

**Compatibility guide:** [src_docs/md/pythonqt-compatibility.md](pythonqt-compatibility.md) lists what
runs unchanged, what is adapted, what is not supported, and the native acceptance
command.

Namespaces load lazily through fontlab-echopy. QtWidgets exposes the 195 native
classes in the verified PySide2 5.15.2.1 intersection. Each known PySide2 name
routes to its joined native module, including QtCore models found in QtGui;
names belonging to other families are excluded. Native extensions remain
available in their original families, and combined Qt remains native.
QObject uses QtCore's native class when present,
otherwise the actual PythonQt.private.QObject. Signals, slots and properties are
routed directly; no fake binding objects are supplied.

QtCore, QtGui, QtWidgets, QtNetwork, QtOpenGL, QtSvg, QtUiTools, QtXmlPatterns and
the native combined Qt namespace are available. Missing members raise
AttributeError. Outside FontLab, Echopy's documentation declarations may load;
constructing native classes raises NativeUnavailable. Names alone do not imply
PySide-compatible callable properties, enums, overloads, ownership or callbacks.
Those differences, full application ports and Qt6 are separately planned.


## Documentation map

Read [installation](installation.md), the [complete PythonQt compatibility guide](pythonqt-compatibility.md), [development and limits](development-and-limits.md), and [licence](licence.md).
