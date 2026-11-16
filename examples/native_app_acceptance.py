# this_file: examples/native_app_acceptance.py
# SPDX-License-Identifier: Apache-2.0
"""Run inside FontLab; controller retains the result for visible-window checks."""

import hashlib
from pathlib import Path

from pythonqtside import AppHandle, run_app
from pythonqtside._app_native import host_application, resolve


def verify_disconnection(handle: AppHandle) -> dict[str, bool | int]:
    """Emit native signals after disconnection while the owned window is still alive."""
    window = handle.namespace["window"]
    count = window.update_count
    text = resolve(window.label, "text")()
    connections_before = len(handle._connections)
    assert connections_before == 2, "both native example connections must be recorded"
    assert not handle._disconnect_callbacks(), (
        "native callback disconnection must succeed"
    )
    window.button.click()
    window.updated.emit("disconnection probe must not reach the label")
    assert window.update_count == count, (
        "disconnected native clicked signal must not invoke Python"
    )
    assert resolve(window.label, "text")() == text, (
        "disconnected custom signal must not update native text"
    )
    assert window.isVisible() and not handle.closed, (
        "disconnection must be verified before owned deletion"
    )
    return {
        "disconnected_before_deletion": True,
        "connections_before": connections_before,
        "connections_after": len(handle._connections),
    }


def run_example(*, close: bool = False):
    """Exercise only the owned example; return the retained handle and evidence."""
    entry = Path(__file__).with_name("unchanged_app") / "app.py"
    paths = (entry, entry.with_name("helper.py"))
    original_hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    host, _ = host_application()
    handle = run_app(entry)
    try:
        window = handle.namespace["window"]
        assert handle.namespace["app"].native_application is host, (
            "host application must be reused"
        )
        assert window.isVisible(), "the owned example must have a visible native window"
        window.button.click()
        assert window.update_count == 1, "native clicked callback must run once"
        assert window.last_width > 0, (
            "width() must read confirmed native property state"
        )
        assert "Unchanged PySide2 callback" in window.last_text, (
            "custom signal and delayed helper must update the label"
        )
        assert len(handle.reports) == 2, (
            "entry and delayed helper must both have provenance"
        )
        for path in paths:
            key = str(path.resolve())
            assert (
                hashlib.sha256(path.read_bytes()).hexdigest()
                == original_hashes[str(path)]
            ), "source bytes must remain unchanged"
            assert handle.reports[key]["source_sha256"] == original_hashes[str(path)], (
                "report hash must identify original bytes"
            )
        evidence = {
            "source_hashes": original_hashes,
            "width": window.last_width,
            "text": window.last_text,
            "updates": window.update_count,
            "application_proxy": handle.identity_report["application_proxy"].__name__,
            "connections_before": len(handle._connections),
        }
        assert evidence["connections_before"] == 2, (
            "both native example connections must be tracked"
        )
        if close:
            evidence.update(verify_disconnection(handle))
            handle.close()
            assert not handle.cleanup_errors, (
                "owned callback disconnection and cleanup must succeed"
            )
        return handle, evidence
    except BaseException:
        handle.close()
        raise
