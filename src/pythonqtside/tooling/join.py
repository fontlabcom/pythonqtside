# this_file: src/pythonqtside/tooling/join.py
"""Join factual surfaces; unknown capture details remain explicitly unknown."""

from .surface import Surface, effective_classes, extract

MODULES = (
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtNetwork",
    "QtOpenGL",
    "QtSvg",
    "QtUiTools",
    "QtXmlPatterns",
)
NATIVE_MODULES = tuple(m for m in MODULES if m != "QtWidgets") + ("private", "Qt")
STATUSES = ("native_same_module", "native_other_module", "private_only", "missing")
_EMPTY = extract("class Absent: pass")["classes"]["Absent"]


def _route(module: str, name: str, native: dict[str, Surface], kind: str) -> dict:
    found = sorted(m for m, data in native.items() if name in data[kind])
    # Prefer the canonical family, then public families, combined Qt, finally private.
    order = [module, "QtGui"] if module == "QtWidgets" else [module]
    order += [m for m in NATIVE_MODULES if m not in {"Qt", "private"}] + [
        "Qt",
        "private",
    ]
    target = next((m for m in order if m in found), None)
    status = "missing" if target is None else "native_other_module"
    if target == module:
        status = "native_same_module"
    elif target == "private":
        status = "private_only"
    return {"native_module": target, "native_locations": found, "status": status}


def _nested_enums(pyside: Surface, native: Surface) -> dict:
    result = {}
    for name in sorted(pyside["enums"].keys() | native["enums"].keys()):
        expected = pyside["enums"].get(name, set())
        actual = native["enums"].get(name, set())
        opaque = name in native["opaque_types"]
        result[name] = {
            "native_layout": "opaque_type"
            if opaque
            else "nested"
            if name in native["enums"]
            else "absent",
            "members_only_pyside": None if opaque else sorted(expected - actual),
            "members_only_native": None if opaque else sorted(actual - expected),
        }
    return result


TUPLE_PREFIXES = ("typing.Tuple[", "Tuple[", "tuple[")


def _tuple_returns(pyside: Surface, native: Surface) -> dict:
    """PySide2 tuple results versus the same-name native declarations (out-parameters)."""
    result = {}
    for name, overloads in sorted(pyside["signatures"].items()):
        returns = sorted(
            {
                s["returns"]
                for s in overloads
                if (s["returns"] or "").startswith(TUPLE_PREFIXES)
            }
        )
        if returns:
            result[name] = {
                "pyside_returns": returns,
                "pyside_overloads": overloads,
                "native_overloads": native["signatures"].get(name),
            }
    return result


def _bool_predicates(native: Surface) -> list[str]:
    return sorted(
        name
        for name, overloads in native["signatures"].items()
        if any(not s["parameters"] and s["returns"] == "bool" for s in overloads)
    )


def differences(pyside: Surface, native: Surface) -> dict:
    """A name difference does not establish callable, value or dispatch compatibility."""
    pa, na = (
        set(pyside["attributes"]) | pyside["properties"],
        set(native["attributes"]) | native["properties"],
    )
    result = {
        "methods_only_pyside": sorted(pyside["methods"] - native["methods"]),
        "methods_only_native": sorted(native["methods"] - pyside["methods"]),
        "attributes_only_pyside": sorted(pa - na),
        "attributes_only_native": sorted(na - pa),
        "native_attributes_for_pyside_accessors": sorted(pyside["getters"] & na),
        "enum_members_only_pyside": sorted(
            pyside["enum_members"] - na - native["enum_members"]
        ),
        "enum_members_only_native": sorted(
            native["enum_members"] - pa - pyside["enum_members"]
        ),
        "enum_members_only_native_candidates": sorted(
            native["enum_candidates"]
            - native["enum_members"]
            - pa
            - pyside["enum_members"]
        ),
        "nested_enums": _nested_enums(pyside, native),
        "tuple_returns": _tuple_returns(pyside, native),
        "nested_classes_only_pyside": sorted(
            pyside["nested_classes"].keys()
            - native["nested_classes"].keys()
            - native["opaque_types"]
        ),
        "nested_classes_only_native": sorted(
            native["nested_classes"].keys() - pyside["nested_classes"].keys()
        ),
    }
    # Predicates are recorded only where a tuple result may need an ok value.
    result["native_bool_predicates"] = (
        _bool_predicates(native) if result["tuple_returns"] else []
    )
    result["nested_classes"] = {
        n: class_details(cls, native["nested_classes"].get(n))
        for n, cls in sorted(pyside["nested_classes"].items())
    }
    return result


def counts(surface: Surface) -> dict[str, int]:
    return {
        name: len(surface[name])
        for name in (
            "methods",
            "properties",
            "attributes",
            "enums",
            "enum_members",
            "opaque_types",
            "nested_classes",
            "constructors",
        )
    }


def class_details(expected: Surface, actual: Surface | None) -> dict:
    return {
        "stub_helper": expected["stub_helper"],
        "counts": {
            "pyside": counts(expected),
            "native": counts(actual) if actual else None,
        },
        "constructors": {
            "pyside": expected["constructors"],
            "native": actual["constructors"] if actual else None,
        },
        "differences": differences(expected, actual or _EMPTY),
    }


def join_surfaces(pyside: dict[str, Surface], native: dict[str, Surface]) -> dict:
    upstream_classes = effective_classes(pyside)
    native_classes = effective_classes(native)
    result = {}
    for module, data in sorted(pyside.items()):
        classes = {}
        for name in sorted(data["classes"]):
            route = _route(module, name, native, "classes")
            expected = upstream_classes[f"{module}.{name}"]
            actual = native_classes.get(f"{route['native_module']}.{name}")
            classes[name] = route | class_details(expected, actual)
        result[module] = {
            "classes": classes,
            "members": {
                n: _route(module, n, native, "members") for n in sorted(data["members"])
            },
            "summary": {
                s: sum(c["status"] == s for c in classes.values()) for s in STATUSES
            },
        }
    return result
