# this_file: tests/test_app_native.py
"""Getter adaptation requires actual native metadata, not a noncallable guess."""

import pytest

from pythonqtside._app_native import resolve


class NativeFixture:
    __module__ = "PythonQt.QtGui"
    text = "native text"

    def metaObject(self):
        return self

    def indexOfProperty(self, name):
        return 1 if name == "text" else -1

    def property(self, name):
        return getattr(self, name)


def test_resolve_when_native_property_exists_then_callable_reads_live_value():
    obj = NativeFixture()
    getter = resolve(obj, "text")
    obj.text = "changed"
    assert getter() == "changed", "getter must read live native state"
    with pytest.raises(TypeError):
        getter(7)


def test_resolve_when_ordinary_value_exists_then_it_stays_noncallable():
    obj = type("Plain", (), {"text": "ordinary"})()
    assert resolve(obj, "text") == "ordinary", (
        "ordinary Python call errors must not be hidden"
    )


def test_resolve_when_super_targets_native_property_then_metadata_reads_base_value():
    class Child(NativeFixture):
        def text(self):
            return resolve(super(), "text")()

    obj = Child()
    obj.property = lambda name: "base text"
    assert obj.text() == "base text", "native properties need explicit super lookup"


def test_resolve_when_native_python_attribute_is_not_a_qt_property_then_call_still_fails():
    obj = NativeFixture()
    obj.ordinary = 17
    with pytest.raises(TypeError):
        resolve(obj, "ordinary")()


def test_resolve_when_native_super_has_missing_bound_method_then_unbound_fallback_works():
    class NativeBase:
        __module__ = "PythonQt.QtGui"

        @staticmethod
        def resize(instance, width):
            instance.width = width

    class Child(NativeBase):
        pass

    obj = Child()

    # PythonQt's missing descriptor path is measured; use a super subclass to
    # reproduce the lookup failure without claiming this fixture is a binding.
    class MissingSuper(super):
        def __getattribute__(self, name):
            if name == "resize":
                raise AttributeError(name)
            return super().__getattribute__(name)

    resolve(MissingSuper(Child, obj), "resize")(42)
    assert obj.width == 42, "fallback must explicitly pass the native instance"


def test_resolve_when_native_super_constructor_is_uninitialized_then_no_metadata_is_queried():
    class UninitializedBase:
        __module__ = "PythonQt.QtGui"

        def __init__(self):
            self.initialized = True

        def metaObject(self):
            if not getattr(self, "initialized", False):
                raise ValueError(
                    "Trying to call metaObject on a destroyed QWidget object"
                )
            return self

    class Child(UninitializedBase):
        def __init__(self):
            resolve(super(), "__init__")()

    assert Child().initialized, (
        "the native base constructor must run before querying Qt metadata"
    )


def test_resolve_when_python_base_shadows_native_property_then_super_value_is_unchanged() -> (
    None
):
    class PythonBase:
        text = 17

    class Child(PythonBase, NativeFixture):
        pass

    assert resolve(super(Child, Child()), "text") == 17, (
        "successful Python base lookup must not become a native property getter"
    )


@pytest.mark.parametrize("binding", ["class", "unbound"])
def test_resolve_when_super_has_no_instance_or_member_then_attribute_error_is_preserved(
    binding: str,
) -> None:
    class Child:
        pass

    receiver = super(Child, Child) if binding == "class" else super(Child)
    with pytest.raises(AttributeError, match="missing"):
        resolve(receiver, "missing")
