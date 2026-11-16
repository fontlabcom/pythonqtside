# this_file: examples/fixtures/run_native.py
# SPDX-License-Identifier: Apache-2.0
"""Run the R036 fixture acceptance in FontLab through fontlab-remopy.

    cd ../fontlab-remopy
    uv run python ../pythonqtside/examples/fixtures/run_native.py \
        --pythonqtside ../pythonqtside/src --echopy ../fontlab-echopy/src [STAGE ...]

``--pythonqtside`` may point at an extracted wheel instead of ``src``. Each stage
is one short ``run_python`` call; waits happen here, between calls, so FontLab's
event loop delivers process output and deferred deletions. Prints one JSON report;
exits 1 if any check fails.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from fontlab_remopy import FontLab
from hostpath import SETUP, TEARDOWN  # sys.path guard run inside FontLab

MODULE = "pqs_fixture_acceptance"

STAGE = "import sys\nresult = getattr(sys.modules[MODULE], stage)()"


def call(fl, code: str, **variables):
    reply = fl.run(code, MODULE=MODULE, **variables)
    if reply.value is None:
        raise RuntimeError(reply.stderr[-2000:] or "no result")
    return reply.value


def poll(fl, stage: str, done, attempts: int = 25, pause: float = 0.2):
    for _ in range(attempts):
        value = call(fl, STAGE, stage=stage)
        if done(value):
            return value
        time.sleep(pause)
    return value


def ok_close(r: dict) -> bool:
    return r["closed"] and not r["cleanup_errors"] and r["sources_unchanged"]


def run_timer(fl) -> dict:
    out = {"start": call(fl, STAGE, stage="timer_start")}
    names = lambda r, kind: {e[1] for e in r["log"] if e[0] == kind}
    out["settled"] = poll(
        fl,
        "timer_poll",
        # Bounded host-side wait (50 x 0.2 s) for the timer and both processes;
        # a busy host can deliver the first tick after the processes settle.
        lambda r: (
            r["ticks"] > 0
            and "/bin/echo" in names(r, "finished")
            and bool(names(r, "error"))
        ),
        attempts=50,
    )
    out["cancel"] = call(fl, STAGE, stage="timer_cancel")
    out["cancelled"] = poll(
        fl, "timer_poll", lambda r: "/bin/sleep" in names(r, "finished")
    )
    out["finish"] = call(fl, STAGE, stage="timer_finish")
    time.sleep(0.3)
    out["after_close"] = call(fl, STAGE, stage="timer_after_close")
    out["close_cancels"] = call(fl, STAGE, stage="timer_close_cancels")
    log = out["cancelled"]["log"]
    out["checks"] = {
        "ticks_ran": out["settled"]["ticks"] > 0,
        "echo_success": ["finished", "/bin/echo", 0, "pythonqtside"] in log,
        "missing_error": any(
            e[0] == "error" and e[1].startswith("/nonexistent") for e in log
        ),
        "sleep_cancelled": any(
            e[0] == "finished" and e[1] == "/bin/sleep" for e in log
        ),
        "timer_stopped_by_close": out["after_close"]["ticks"]
        == out["finish"]["ticks_at_close"],
        "closed": ok_close(out["finish"]),
        "close_kills_process": ok_close(out["close_cancels"])
        and out["close_cancels"]["sleeper_state_after_close"] == 0,
    }
    return out


def run_lifetime(fl) -> dict:
    out = {"open": call(fl, STAGE, stage="lifetime_open")}
    out["close_child"] = call(fl, STAGE, stage="lifetime_close_child")
    out["destroyed"] = poll(fl, "lifetime_poll", lambda r: r["destroyed_children"] == 1)
    out["reopen"] = call(fl, STAGE, stage="lifetime_reopen")
    time.sleep(0.2)
    out["after_close"] = call(fl, STAGE, stage="lifetime_after_close")
    out["checks"] = {
        "opened_visible": out["open"] == {"opened": 1, "child_visible": True},
        "delete_on_close_destroyed": out["destroyed"]
        == {"destroyed_children": 1, "child_cleared": True},
        "reopened": out["reopen"]["opened"] == 2 and out["reopen"]["child_visible"],
        "closed": ok_close(out["reopen"]),
        "deleted_after_close": out["after_close"]
        == {"main": "destroyed", "child": "destroyed"},
    }
    return out


def checks(stage: str, r: dict) -> dict:
    if stage == "form":
        return {
            "values": r["values"]
            == {"name": "Aring", "size": 48, "style": "Bold", "outline": True},
            "accepted": r["dialog_result"] == 1 and r["hidden_after_accept"],
            "closed": ok_close(r),
        }
    if stage == "signals":
        return {
            "slot": r["label_after_slot"] == "1",
            "property": r["property_index"] >= 0 and r["property_read"] == 1,
            "property_notify": r["set_property"]
            and r["label_after_set_property"] == "5",
            "event_filter": r["filter_keys"] == [65, 88]
            and r["edit_text_x_swallowed"] == "a",
            "no_callback_after_close": r["label_after_close_emit"] == "5",
            "reentry_after_close": r["reentry_after_close"]
            == "The embedded application handle is closed",
            "deleted_after_close": r["after_close"]
            == {"panel": "destroyed", "label": "destroyed"},
            "overrides": "show" in r["events"]
            and ["resize", 300] in r["events"]
            and ["key", 66] in r["events"]
            and "close" in r["events"],
            "closed": ok_close(r),
        }
    if stage == "modelview":
        return {
            "model_via_native": r["display_via_native_index"] == 600 and r["editable"],
            "header": r["header"] == "Advance",
            "delegate_editor": r["editor"] == "QSpinBox",
            "edited": r["after_edit"] == 640 and r["rows"][0][1] == 640,
            "closed": ok_close(r),
        }
    if stage == "uiloader":
        return {
            "loaded": r["class"] == "QWidget" and r["title"] == "Greeting",
            "loaded_widget_owned": r["owned_by_handle"],
            "wired": r["status"] == "Hello, Ada",
            "closed": ok_close(r),
        }
    if stage == "painter":
        return {
            "input": r["points"] == 1 and r["paints"] >= 1,
            "red_point": r["click_pixel"] == "#ff0000",
            "white_background": r["background_pixel"] == "#ffffff",
            "closed": ok_close(r),
        }
    return {}


SIMPLE = ("form", "signals", "modelview", "uiloader", "painter")
ALL = (*SIMPLE, "timer_process", "lifetime")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pythonqtside", type=Path, required=True)
    parser.add_argument("--echopy", type=Path, required=True)
    parser.add_argument("stages", nargs="*", default=list(ALL))
    args = parser.parse_args()
    paths = {
        "pqs": str(args.pythonqtside.resolve()),
        "echo": str(args.echopy.resolve()),
    }
    report = {}
    with FontLab() as fl:
        try:
            report["setup"] = call(
                fl,
                SETUP,
                harness=str(Path(__file__).resolve().with_name("acceptance.py")),
                **paths,
            )
            for stage in args.stages:
                try:
                    if stage == "timer_process":
                        report[stage] = run_timer(fl)
                    elif stage == "lifetime":
                        report[stage] = run_lifetime(fl)
                    elif stage == "signals":
                        r = call(fl, STAGE, stage="signals")
                        time.sleep(0.2)
                        r["after_close"] = call(fl, STAGE, stage="signals_after_close")
                        report[stage] = r | {"checks": checks(stage, r)}
                    elif stage == "modelview":
                        r = call(fl, STAGE, stage="modelview")
                        time.sleep(0.2)
                        r |= call(fl, STAGE, stage="modelview_check")
                        report[stage] = r | {"checks": checks(stage, r)}
                    else:
                        r = call(fl, STAGE, stage=stage)
                        report[stage] = r | {"checks": checks(stage, r)}
                except Exception as error:  # noqa: BLE001 - record and continue
                    report[stage] = {
                        "error": str(error)[-1500:],
                        "checks": {"ran": False},
                    }
                    report[stage]["abort"] = call(fl, STAGE, stage="abort")
        finally:
            call(fl, TEARDOWN, **paths)
    report["passed"] = all(
        all(report[s]["checks"].values()) for s in args.stages if s in report
    )
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
