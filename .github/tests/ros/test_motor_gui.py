"""SDK position GUI with fake Tk: no display, CAN or control commands."""
from types import SimpleNamespace as NS

import pytest

from motomind_milly.monitor import MotorMonitor


def config():
    return NS(buses=[], motors=[NS(id=i, joint_name=f"joint_{i}", run_mode=0) for i in range(1, 8)])


def test_position_rows_do_not_invent_feedback():
    rows = {1: {"position": -.42, "age_s": .02, "fresh": True},
            7: {"position": 1.5, "age_s": 2., "fresh": False}}
    gui = MotorMonitor(object(), config(), position_snapshot=lambda: rows)
    values = gui._position_rows()
    assert len(values) == 7
    assert values[0] == ((1, "joint_1", "-0.4200", "0.020", "FRESH"), "fresh")
    assert values[1] == ((2, "joint_2", "—", "—", "MISSING"), "missing")
    assert values[-1] == ((7, "joint_7", "+1.5000", "2.000", "STALE"), "stale")


def test_position_view_cannot_own_arm():
    with pytest.raises(ValueError, match="owns_arm=False"):
        MotorMonitor(object(), config(), owns_arm=True, position_snapshot=lambda: {})


@pytest.mark.parametrize('full_feedback', [False, True])
def test_position_window_has_no_buttons_or_manager_calls(monkeypatch, full_feedback):
    import tkinter as tk
    from tkinter import ttk
    events, displayed = [], []
    class Root:
        def title(self, title): pass
        def after(self, delay, callback): events.append(callback)
        def protocol(self, event, callback): self.on_close = callback
        def destroy(self): self.destroyed = True
        def mainloop(self):
            events.pop(0)()
            self.on_close()
            events.pop(0)()
    class Widget:
        def __init__(self, *a, **kw): pass
        def pack(self, **kw): pass
        def heading(self, *a, **kw): pass
        def column(self, *a, **kw): pass
        def tag_configure(self, *a, **kw): pass
        def get_children(self): return []
        def delete(self, *a): pass
        def insert(self, *a, **kw): displayed.append(kw["values"])
    root = Root()
    monkeypatch.setattr(tk, "Tk", lambda: root)
    monkeypatch.setattr(ttk, "Label", Widget)
    monkeypatch.setattr(ttk, "Treeview", Widget)
    def no_button(*a, **kw): pytest.fail("passive view must not have control buttons")
    monkeypatch.setattr(tk, "Button", no_button)
    monkeypatch.setattr(ttk, "Button", no_button)
    # object() deliberately has NO manager API: even reading it is unnecessary.
    callback = {'feedback_snapshot' if full_feedback else 'position_snapshot': lambda: {}}
    gui = MotorMonitor(object(), config(), **callback)
    gui.run()
    assert root.destroyed and gui._closed.is_set()
    assert len(displayed) == 7 and all(row[-1] == "MISSING" for row in displayed)


def test_full_feedback_values_missing_stale_and_fault():
    row = dict(position=-.42, velocity=.06, torque=1.234, temperature=37.5,
               fault_bits=0, mode_status=2, age_s=.02, fresh=True)
    rows = {1: row, 7: dict(row, fault_bits=4, age_s=2., fresh=False)}
    gui = MotorMonitor(object(), config(), feedback_snapshot=lambda: rows)
    values = gui._feedback_rows()
    assert values[0] == ((1, 'joint_1', '-0.4200', '+0.0600', '+1.234', '37.5',
                          '0x0', 2, '0.020', 'FRESH'), 'fresh')
    assert values[1][0][2:9] == ('—',) * 7
    assert values[1][1] == 'missing'
    assert values[-1][0][-1] == 'STALE / FAULT'
    assert values[-1][1] == 'fault'
    rows[1] = dict(row, torque=None, temperature=float('nan'))
    assert gui._feedback_rows()[0][0][4:6] == ('—', '—')
    with pytest.raises(ValueError):
        MotorMonitor(object(), config(), owns_arm=True, feedback_snapshot=lambda: {})
    with pytest.raises(ValueError):
        MotorMonitor(object(), config(), position_snapshot=lambda: {}, feedback_snapshot=lambda: {})


def test_start_reports_display_failure(monkeypatch):
    gui = MotorMonitor(object(), config(), position_snapshot=lambda: {})
    def fail(): raise RuntimeError("no display")
    monkeypatch.setattr(gui, "run", fail)
    with pytest.raises(RuntimeError, match="no display"):
        gui.start(wait=True)
    gui.close(wait=True)
