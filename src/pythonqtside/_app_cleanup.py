# this_file: src/pythonqtside/_app_cleanup.py
"""Disconnect and stop owned work before deleting roots of the owned graph."""

import inspect
from collections.abc import Callable
from functools import partial
from typing import Any

from . import _app_native


def native_slot(value: Any) -> bool:
    """A bound native Qt slot, such as ``dialog.reject`` (measured type name)."""
    return type(value).__name__ == "builtin_qt_slot"


def same(left: Any, right: Any) -> bool:
    """Equality that never lets PythonQt compare a native slot with another type.

    PythonQt's slot comparison casts both operands to slot objects; comparing a
    native slot with a bound method of the same object segfaults FontLab
    (pqs-g04/fixtures/crash2-disconnect.md)."""
    return left is right or (type(left) is type(right) and bool(left == right))


def _same_args(left: tuple, right: tuple) -> bool:
    return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))


def slot_forwarder(slot: Any) -> Callable:
    """Connect a native slot through a Python function.

    PythonQt passes every signal argument to a native slot, so
    ``clicked.connect(label.clear)`` fails with "wrong number of arguments"; Qt
    drops trailing arguments the slot does not take. The forwarder retries with
    fewer leading arguments and remembers the count that worked. Holding only
    Python functions in PythonQt's handler list also keeps its disconnect
    comparison away from native slots."""
    accepted: list[int] = []

    def forward(*args: Any) -> Any:
        if accepted:
            return slot(*args[: accepted[0]])
        for count in range(len(args), -1, -1):
            try:
                result = slot(*args[:count])
            except ValueError as error:
                message = str(error)
                if count and (
                    "wrong number of arguments" in message
                    or "Could not find matching overload" in message
                ):
                    continue
                raise
            accepted.append(count)
            return result
        return None

    forward.__wrapped__ = slot
    return forward


def _required(callback: Any) -> int | None:
    """Positional parameters a Python callback needs; None for *args or unknown."""
    try:
        parameters = inspect.signature(callback).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_POSITIONAL for p in parameters):
        return None
    return sum(
        p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty
        for p in parameters
    )


def overload_signature(signal: Any, name: str, callback: Any) -> str | None:
    """``"2finished(int,QProcess::ExitStatus)"`` when the callback needs more
    arguments than PythonQt's default (first declared) overload delivers.

    PythonQt connects ``process.finished`` to the deprecated ``finished(int)``, so a
    PySide2 ``lambda code, status: ...`` never runs (pqs-g04/fixtures)."""
    required = _required(callback)
    if required is None:
        return None
    try:
        overloads = [tuple(types) for types in signal.parameterTypes()]
    except Exception:  # noqa: BLE001 - not a PythonQt signal wrapper
        return None
    if len(overloads) < 2 or required <= len(overloads[0]):
        return None
    fits = [types for types in overloads if len(types) >= required]
    if not fits:
        return None
    return "2" + name + "(" + ",".join(min(fits, key=len)) + ")"


def connection_call(
    receiver: Any,
    name: str,
    value: Any,
    records: list[tuple],
    owner: Any = None,
    signal_name: str | None = None,
) -> Callable:
    """Track successful native connects and mirror explicit disconnects.

    Records are ``(signal, args, kwargs, undo, owner)``; ``undo`` disconnects an
    overload-specific connection made through ``owner.connect(signature, ...)``;
    ``owner`` is the signal's QObject when the call site named it."""

    def connect(*args: Any, **kwargs: Any) -> Any:
        if args and native_slot(args[0]):
            args = (slot_forwarder(args[0]), *args[1:])
        signature = (
            overload_signature(receiver, signal_name, args[0])
            if owner is not None and signal_name and len(args) == 1 and not kwargs
            else None
        )
        if signature is not None and owner.connect(signature, args[0]):
            undo = partial(owner.disconnect, signature, args[0])
            records.append((receiver, args, {}, undo, owner))
            return True
        result = value(*args, **kwargs)
        if result is not False:
            records.append((receiver, args, dict(kwargs), None, owner))
        return result

    def disconnect(*args: Any, **kwargs: Any) -> Any:
        mine = [
            r for r in records if _app_native.same_connection_receiver(r[0], receiver)
        ]
        if args and native_slot(args[0]):
            wrapped = [
                r for r in mine if same(getattr(r[1][0], "__wrapped__", None), args[0])
            ]
            if not wrapped:
                return False  # PythonQt would compare the slot with every handler
            args = (wrapped[0][1][0], *args[1:])
        matched = [
            r for r in mine if not args or (_same_args(r[1], args) and r[2] == kwargs)
        ]
        undone = [r for r in matched if r[3] is not None]
        for record in undone:
            record[3]()
        # Only overload connections made through owner.connect() are undone here;
        # everything else, including callbacks this handle never tracked, goes to
        # PythonQt (native-slot arguments were mapped or refused above).
        result = (
            True if undone and len(undone) == len(matched) else value(*args, **kwargs)
        )
        if result is not False:
            records[:] = [r for r in records if not any(r is m for m in matched)]
        return result

    return connect if name == "connect" else disconnect


def disconnect_connections(connections: list[tuple]) -> tuple[str, ...]:
    """Disconnect tracked callbacks independently of owned native object deletion."""
    errors = []
    for receiver, args, kwargs, undo, owner in reversed(connections):
        try:
            if owner is not None and _app_native.destroyed(owner):
                continue  # Qt deleted the sender; its PythonQt handlers went with it
            if undo is not None:
                undo()
            else:
                receiver.disconnect(*args, **kwargs)
        except Exception as error:  # noqa: BLE001 - record host-specific teardown failures
            errors.append(f"{type(error).__name__}: {error}")
    return tuple(errors)


def cleanup(
    objects: list[Any], connections: list[tuple]
) -> tuple[tuple[str, ...], list[Any]]:
    errors = list(disconnect_connections(connections))
    # Qt may already have deleted owned objects (a delegate's editor); their
    # wrappers raise on use, so they are gone rather than cleanup failures.
    objects = [obj for obj in objects if not _app_native.destroyed(obj)]

    def attempt(action: Callable[[], Any]) -> None:
        try:
            action()
        except Exception as error:  # noqa: BLE001 - teardown must retain the original startup error
            errors.append(f"{type(error).__name__}: {error}")

    unstopped = []
    for obj in objects:
        try:
            _app_native.stop_owned(obj)
        except Exception as error:  # noqa: BLE001 - cleanup failures are reported without masking startup errors
            errors.append(f"{type(error).__name__}: {error}")
            unstopped.append(obj)
    # Never delete an owned ancestor of work that failed to stop.
    for obj in tuple(unstopped):
        try:
            parent = obj.parent()
            while parent is not None and any(parent is owned for owned in objects):
                if not any(parent is kept for kept in unstopped):
                    unstopped.append(parent)
                parent = parent.parent()
        except Exception as error:  # noqa: BLE001 - teardown cannot replace an execution error
            errors.append(f"{type(error).__name__}: {error}")
            unstopped[:] = objects
    for obj in objects:
        try:
            root = not any(obj.parent() is owned for owned in objects)
        except Exception as error:  # noqa: BLE001 - already-deleted native wrappers can fail in host-specific ways
            errors.append(f"{type(error).__name__}: {error}")
            continue
        if root and not any(obj is live for live in unstopped):
            attempt(partial(_app_native.close_owned_widget, obj))
            attempt(lambda obj=obj: obj.deleteLater())
    return tuple(errors), unstopped
