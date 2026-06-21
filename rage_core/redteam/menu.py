"""
Interactive curses menu for the RAGE red-team runner.

Phase A — Configuration screen (before launch):
  Navigate with arrow keys, toggle checkboxes with Space,
  adjust numbers with Up/Down, confirm with Enter.

Phase B — Live control panel (while the loop runs in a background thread):
  Displays real-time iteration status; hotkeys S/P/M/V/Q.

Falls back gracefully when curses is unavailable (e.g. piped output).
"""

from __future__ import annotations

import curses
import queue
import textwrap
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rage_core.redteam.loop import IterationStatus, RedTeamConfig
    from rage_core.redteam.vulnerability_db import VulnerabilityDB

ALL_OBJECTIVES = ["exfil", "ddl", "schema_dump", "canary", "privilege"]
ALL_MODELS = ["offline", "gpt-4o-mini", "gpt-4o"]

SCALE_PRESETS = {
    "light": {"iterations": 5,  "max_turns": 8,  "max_backtracks": 5},
    "medio": {"iterations": 20, "max_turns": 12, "max_backtracks": 10},
    "heavy": {"iterations": 50, "max_turns": 20, "max_backtracks": 10},
}


# --------------------------------------------------------------------------- #
# Phase A — configuration                                                     #
# --------------------------------------------------------------------------- #

class ConfigMenu:
    """Curses-based configuration screen. Returns a RedTeamConfig on ENTER."""

    def __init__(self) -> None:
        self._scale_idx = 1  # medio
        self._iterations = 20
        self._max_turns = 12
        self._max_backtracks = 10
        self._objectives = [True, True, False, False, False]
        self._model_idx = 0  # offline
        self._auto_patch = True
        self._patch_retry = True
        self._cursor = 0

    def run(self) -> "RedTeamConfig | None":
        """Open curses screen; return config or None if user pressed Q."""
        try:
            return curses.wrapper(self._draw)
        except curses.error:
            return self._headless_fallback()

    # ------------------------------------------------------------------ #

    def _draw(self, stdscr: curses.window) -> "RedTeamConfig | None":
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)    # selected
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)    # header
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)   # on
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)     # off
        stdscr.keypad(True)

        FIELDS = [
            "scale", "iterations", "max_turns", "max_backtracks",
            *[f"obj_{o}" for o in ALL_OBJECTIVES],
            "model", "auto_patch", "patch_retry",
        ]

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            self._render(stdscr, w, FIELDS)
            stdscr.refresh()

            key = stdscr.getch()
            result = self._handle_key(key, FIELDS)
            if result == "quit":
                return None
            if result == "start":
                return self._build_config()

    def _render(self, stdscr: curses.window, w: int, fields: list[str]) -> None:
        title = " RAGE Red-Team — Configuracion "
        stdscr.addstr(0, max(0, (w - len(title)) // 2), title, curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(1, 0, "─" * min(w - 1, 54))

        row = 2
        scale_name = list(SCALE_PRESETS.keys())[self._scale_idx]

        items = [
            ("scale",         f"Escala             : [{scale_name:6s}] ◄►  (light/medio/heavy)"),
            ("iterations",    f"Iteraciones        : [{self._iterations:4d}] ▲▼"),
            ("max_turns",     f"Turnos/iteracion   : [{self._max_turns:4d}] ▲▼"),
            ("max_backtracks",f"Backtracks max     : [{self._max_backtracks:4d}] ▲▼"),
        ] + [
            (f"obj_{o}", f"  Objetivo [{' x' if self._objectives[i] else '  '}] {o}")
            for i, o in enumerate(ALL_OBJECTIVES)
        ] + [
            ("model",       f"Modelo LLM         : [{ALL_MODELS[self._model_idx]:12s}] ▲▼"),
            ("auto_patch",  f"Auto-patch         : [{'ON ' if self._auto_patch else 'OFF'}]  (SPACE)"),
            ("patch_retry", f"Patch-and-retry    : [{'ON ' if self._patch_retry else 'OFF'}]  (SPACE)"),
        ]

        for idx, (fid, label) in enumerate(items):
            attr = curses.color_pair(1) if idx == self._cursor else 0
            try:
                stdscr.addstr(row + idx, 2, label[:min(w - 3, 60)], attr)
            except curses.error:
                pass

        footer_row = row + len(items) + 1
        try:
            stdscr.addstr(footer_row, 0, "─" * min(w - 1, 54))
            stdscr.addstr(footer_row + 1, 2,
                          "[ENTER] Iniciar   [Q] Salir   [↑↓] Navegar   [←→/SPACE] Cambiar")
        except curses.error:
            pass

    def _handle_key(self, key: int, fields: list[str]) -> str:
        n = len(fields)
        field = fields[self._cursor] if self._cursor < n else ""

        if key == curses.KEY_DOWN:
            self._cursor = (self._cursor + 1) % n
        elif key == curses.KEY_UP:
            self._cursor = (self._cursor - 1) % n
        elif key in (curses.KEY_ENTER, 10, 13):
            return "start"
        elif key in (ord("q"), ord("Q")):
            return "quit"
        elif field == "scale":
            if key in (curses.KEY_RIGHT, ord(" ")):
                self._scale_idx = (self._scale_idx + 1) % 3
                self._apply_scale()
            elif key == curses.KEY_LEFT:
                self._scale_idx = (self._scale_idx - 1) % 3
                self._apply_scale()
        elif field in ("iterations", "max_turns", "max_backtracks"):
            self._adjust_int(field, key)
        elif field.startswith("obj_"):
            if key in (curses.KEY_RIGHT, curses.KEY_LEFT, ord(" ")):
                idx = ALL_OBJECTIVES.index(field[4:])
                self._objectives[idx] = not self._objectives[idx]
        elif field == "model":
            if key in (curses.KEY_UP, curses.KEY_DOWN, ord(" ")):
                self._model_idx = (self._model_idx + 1) % len(ALL_MODELS)
        elif field in ("auto_patch", "patch_retry"):
            if key in (curses.KEY_RIGHT, curses.KEY_LEFT, ord(" ")):
                if field == "auto_patch":
                    self._auto_patch = not self._auto_patch
                else:
                    self._patch_retry = not self._patch_retry
        return "continue"

    def _adjust_int(self, field: str, key: int) -> None:
        delta = 1 if key == curses.KEY_UP else (-1 if key == curses.KEY_DOWN else 0)
        if field == "iterations":
            self._iterations = max(1, self._iterations + delta)
        elif field == "max_turns":
            self._max_turns = max(2, self._max_turns + delta)
        elif field == "max_backtracks":
            self._max_backtracks = max(0, self._max_backtracks + delta)

    def _apply_scale(self) -> None:
        scale = list(SCALE_PRESETS.keys())[self._scale_idx]
        p = SCALE_PRESETS[scale]
        self._iterations = p["iterations"]
        self._max_turns = p["max_turns"]
        self._max_backtracks = p["max_backtracks"]

    def _build_config(self) -> "RedTeamConfig":
        from rage_core.redteam.loop import RedTeamConfig
        chosen_objectives = [o for o, on in zip(ALL_OBJECTIVES, self._objectives) if on] or ["exfil"]
        return RedTeamConfig(
            iterations=self._iterations,
            max_turns=self._max_turns,
            max_backtracks=self._max_backtracks,
            objectives=chosen_objectives,
            model=ALL_MODELS[self._model_idx],
            auto_patch=self._auto_patch,
            patch_and_retry=self._patch_retry,
            scale=list(SCALE_PRESETS.keys())[self._scale_idx],
        )

    def _headless_fallback(self) -> "RedTeamConfig":
        """Used when curses is unavailable."""
        from rage_core.redteam.loop import RedTeamConfig
        return RedTeamConfig()


# --------------------------------------------------------------------------- #
# Phase B — live control panel                                                #
# --------------------------------------------------------------------------- #

class LivePanel:
    """
    Curses live panel shown while the red-team loop runs in a background thread.

    Reads IterationStatus from status_queue and repaints at ~4 Hz.
    Hotkeys are handled in the main thread (getch is non-blocking).
    """

    def __init__(
        self,
        config: "RedTeamConfig",
        stop_event: threading.Event,
        pause_event: threading.Event,
        model_queue: "queue.Queue[str]",
        status_queue: "queue.Queue[IterationStatus]",
        vuln_db: "VulnerabilityDB",
    ) -> None:
        self._config = config
        self._stop = stop_event
        self._pause = pause_event
        self._model_q = model_queue
        self._status_q = status_queue
        self._vuln_db = vuln_db
        self._last_status: "IterationStatus | None" = None
        self._show_vulns = False

    def run(self) -> None:
        try:
            curses.wrapper(self._draw_loop)
        except curses.error:
            self._plain_loop()

    # ------------------------------------------------------------------ #

    def _draw_loop(self, stdscr: curses.window) -> None:
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        stdscr.nodelay(True)
        stdscr.keypad(True)

        while not self._stop.is_set():
            # Drain latest status
            try:
                while True:
                    self._last_status = self._status_q.get_nowait()
            except queue.Empty:
                pass

            stdscr.clear()
            h, w = stdscr.getmaxyx()

            if self._show_vulns:
                self._render_vulns(stdscr, w)
            else:
                self._render_panel(stdscr, w)

            stdscr.refresh()
            key = stdscr.getch()
            self._handle_key(key, stdscr, w)
            curses.napms(250)

    def _render_panel(self, stdscr: curses.window, w: int) -> None:
        s = self._last_status
        title = " RAGE Red-Team — Panel de Control "
        try:
            stdscr.addstr(0, max(0, (w - len(title)) // 2), title,
                          curses.color_pair(2) | curses.A_BOLD)
            if s:
                iter_info = f"  iter {s.iteration}/{s.total_iterations}  |  modelo: {s.model}"
                stdscr.addstr(0, min(w - len(iter_info) - 1, w - 1), iter_info)

            stdscr.addstr(1, 0, "─" * min(w - 1, 60))
            row = 2
            if s:
                band_color = (
                    curses.color_pair(4) if s.band == "block"
                    else curses.color_pair(5) if s.band == "warn"
                    else curses.color_pair(3)
                )
                stdscr.addstr(row,     2, f"Objetivo actual : {s.objective}")
                stdscr.addstr(row + 1, 2,
                              f"Turno           : {s.turn}/{s.max_turns}  |  "
                              f"band: ", 0)
                stdscr.addstr(s.band.upper(), band_color)
                stdscr.addstr(f"  score: {s.score:.1f}")
                stdscr.addstr(row + 2, 2,
                              f"Bypasses totales: {s.total_bypasses}  |  Patched: {s.total_patched}")
                if self._pause.is_set():
                    stdscr.addstr(row + 3, 2, "[ PAUSADO ]", curses.color_pair(5) | curses.A_BOLD)
            else:
                stdscr.addstr(row, 2, "Esperando primera iteracion…")

            stdscr.addstr(row + 5, 0, "─" * min(w - 1, 60))
            stdscr.addstr(row + 6, 2,
                          "[S] Stop  [P] Pause/Resume  [M] Cambiar modelo")
            stdscr.addstr(row + 7, 2,
                          "[V] Ver vulnerabilidades    [Q] Salir seguro")
        except curses.error:
            pass

    def _render_vulns(self, stdscr: curses.window, w: int) -> None:
        vulns = self._vuln_db.all()
        try:
            stdscr.addstr(0, 2, " Vulnerabilidades encontradas ", curses.color_pair(2) | curses.A_BOLD)
            stdscr.addstr(1, 0, "─" * min(w - 1, 60))
            if not vulns:
                stdscr.addstr(2, 2, "(ninguna aún)")
            for i, v in enumerate(vulns[-10:]):
                patch = "✓" if v.patch_applied else "✗"
                line = f"[{patch}] {v.id}  {v.objective}  turn:{v.bypass_turn}  score:{v.pipeline_score:.0f}"
                try:
                    stdscr.addstr(2 + i, 2, line[:min(w - 3, 70)])
                except curses.error:
                    break
            stdscr.addstr(min(14, stdscr.getmaxyx()[0] - 1), 2, "[V] Volver al panel")
        except curses.error:
            pass

    def _handle_key(self, key: int, stdscr: curses.window, w: int) -> None:
        if key == ord("s") or key == ord("S"):
            self._stop.set()
        elif key == ord("q") or key == ord("Q"):
            self._stop.set()
        elif key == ord("p") or key == ord("P"):
            if self._pause.is_set():
                self._pause.clear()
            else:
                self._pause.set()
        elif key == ord("m") or key == ord("M"):
            self._model_swap_submenu(stdscr, w)
        elif key == ord("v") or key == ord("V"):
            self._show_vulns = not self._show_vulns

    def _model_swap_submenu(self, stdscr: curses.window, w: int) -> None:
        models = ALL_MODELS
        idx = 0
        while True:
            stdscr.clear()
            try:
                stdscr.addstr(0, 2, " Seleccionar modelo LLM ", curses.color_pair(2) | curses.A_BOLD)
                for i, m in enumerate(models):
                    attr = curses.color_pair(1) if i == idx else 0
                    stdscr.addstr(2 + i, 4, m, attr)
                stdscr.addstr(2 + len(models) + 1, 2, "[↑↓] Navegar  [ENTER] Confirmar  [ESC] Cancelar")
            except curses.error:
                pass
            stdscr.refresh()
            key = stdscr.getch()
            if key == curses.KEY_DOWN:
                idx = (idx + 1) % len(models)
            elif key == curses.KEY_UP:
                idx = (idx - 1) % len(models)
            elif key in (curses.KEY_ENTER, 10, 13):
                self._model_q.put(models[idx])
                break
            elif key == 27:  # ESC
                break

    # ------------------------------------------------------------------ #
    # Plain-text fallback (no curses)                                     #
    # ------------------------------------------------------------------ #

    def _plain_loop(self) -> None:
        import sys
        import time
        print("\n[RAGE Red-Team] Panel de control en modo texto. Ctrl+C para detener.\n")
        while not self._stop.is_set():
            try:
                status = self._status_q.get(timeout=1.0)
                print(
                    f"  iter {status.iteration}/{status.total_iterations} | "
                    f"obj={status.objective} | turn={status.turn}/{status.max_turns} | "
                    f"band={status.band} score={status.score:.1f} | "
                    f"bypasses={status.total_bypasses} patched={status.total_patched}",
                    flush=True,
                )
            except queue.Empty:
                pass
            except KeyboardInterrupt:
                self._stop.set()
