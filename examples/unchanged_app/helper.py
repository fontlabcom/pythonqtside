# this_file: examples/unchanged_app/helper.py
# SPDX-License-Identifier: Apache-2.0
"""Delayed local import with native class identity retained in the same context."""

from PySide2.QtWidgets import QLabel


def message(width: int) -> str:
    return f"Unchanged PySide2 callback: width {width}, label {QLabel.__name__}"
