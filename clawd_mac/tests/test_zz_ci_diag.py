# -*- coding: utf-8 -*-
"""CI diagnostics (fork check branch only, never in the PR): what a CI Mac does with nice, synthetic scrolls and a
status-item click.  Prints; always passes."""
import os
import platform
import subprocess
import sys

import AppKit
from AppKit import NSScreen, NSStatusBar
from Foundation import NSMakePoint

from clawd_mac import win32_input as mouse
from clawd_mac import win32_loop as loop
from clawd_mac import win32_synthetic as synth
from clawd_mac import win32_tray as tray
from test_win32 import picture, place
from test_win32_tray import RED, add, click_button, icon_pixels, kit, pet  # noqa: F401 (fixtures)


def say(*a):
    print("DIAG", *a, flush=True)


def test_diag_platform():
    say("macOS", platform.mac_ver()[0], platform.machine(), "python", sys.version.split()[0])
    say("screens", [(tuple(s.frame().origin), tuple(s.frame().size), s.backingScaleFactor()) for s in NSScreen.screens()])
    say("status bar thickness", NSStatusBar.systemStatusBar().thickness())


def test_diag_nice():
    say("parent getpriority", os.getpriority(os.PRIO_PROCESS, 0))
    r = subprocess.run(["/usr/bin/nice", "-n", "10", sys.executable, "-I", "-c",
                        "import os; print('child', os.getpriority(os.PRIO_PROCESS, 0))"],
                       capture_output=True, text=True)
    say("nice rc", r.returncode, "out", repr(r.stdout), "err", repr(r.stderr))
    r = subprocess.run(["/bin/ps", "-o", "pid,nice,pri,command", "-p", str(os.getpid())], capture_output=True, text=True)
    say("ps self", repr(r.stdout))


def test_diag_scroll(kit, pet):
    x, y = place()
    hw, _, _ = kit.layered(x, y, 64, 48, picture(64, 48, 64))
    seen = []
    real = mouse._wheel
    mouse._wheel = lambda win, ev: (seen.append(("wheel", ev.type(), ev.window(), ev.scrollingDeltaY(),
                                                 ev.hasPreciseScrollingDeltas())), real(win, ev))[1]
    try:
        panel, ev = synth.scroll_event(hw, x + 10, y + 12, 2, flags=synth.CONTROL)
        say("scroll event type", ev.type(), "window", ev.window(), "panel", panel, "wnum", ev.windowNumber(),
            panel.windowNumber(), "dy", ev.scrollingDeltaY(), "ignores", panel.ignoresMouseEvents())
        panel.sendEvent_(ev)
        say("after panel.sendEvent_: wheel calls", seen, "WM_MOUSEWHEEL", kit.rec.of(pet.WM_MOUSEWHEEL))
        del seen[:]
        panel.contentView().scrollWheel_(ev)
        say("after view.scrollWheel_: wheel calls", seen, "WM_MOUSEWHEEL", kit.rec.of(pet.WM_MOUSEWHEEL))
        hit = panel.contentView().hitTest_(panel.contentView().convertPoint_fromView_(ev.locationInWindow(), None))
        say("hitTest at event", hit, "contentView", panel.contentView())
    finally:
        mouse._wheel = real


def test_diag_status_click(kit, pet, monkeypatch):
    s = pet.GetSystemMetrics(pet.SM_CXSMICON)
    icon = pet.Tray._icon(icon_pixels(s, RED), s)
    hwnd = kit.window(0, 0, 0, 0, ex=pet.WS_EX_TOOLWINDOW)
    button = add(pet, hwnd, icon).button()
    loop.run_for(0.2)
    say("button window", button.window(), "frame", tuple(button.window().frame().origin),
        tuple(button.window().frame().size), "bounds", tuple(button.bounds().size),
        "class", type(button.window()).__name__, "wnum", button.window().windowNumber())
    got = []
    real = tray.anchor

    def spy(b, ev):
        cur = AppKit.NSApp().currentEvent()
        got.append(("event", None if ev is None else (ev.type(), ev.window(), tuple(ev.locationInWindow())),
                    "button.window", b.window(), "same", ev is not None and ev.window() is b.window(),
                    "eq", ev is not None and ev.window() == b.window(),
                    "current", None if cur is None else (cur.type(), cur.window())))
        return real(b, ev)

    monkeypatch.setattr(tray, "anchor", spy)
    monkeypatch.setattr(tray, "_pointer", lambda: NSMakePoint(500.0, NSScreen.screens()[0].frame().size.height - 5))
    click_button(button, AppKit.NSEventTypeLeftMouseDown, AppKit.NSEventTypeLeftMouseUp, 0)
    say("anchor saw", got, "click state", tray._state["click"])
