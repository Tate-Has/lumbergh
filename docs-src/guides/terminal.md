---
title: Terminal
---

# Terminal

The terminal occupies the left pane of the session detail view. It gives you a live, interactive connection to the AI's tmux session via xterm.js and WebSockets.

## Quick Input Bar

At the bottom of the terminal is a text input bar for sending text to the session without clicking into the terminal itself.

Two send modes:

- **Send text only** -- sends the text without a trailing newline. Useful for composing multi-line input before executing.
- **Send with Enter** -- sends the text followed by a newline, executing it immediately.

## Text Selection

!!! important "Hold Shift to select text"
    Tmux captures mouse events by default, which means normal click-and-drag selects text *inside tmux* rather than in your browser.

    - **Shift + click/drag** -- select text in the browser (for copying)
    - **Shift + right-click** -- open the browser's context menu (for paste)

## Pasting

`Ctrl+V` (`Cmd+V` on macOS) pastes into the terminal, as does `Ctrl+Shift+V`.

This differs from a bare xterm.js, which sends a literal `^V` and reserves paste for
`Ctrl+Shift+V`. That default silently breaks dictation and clipboard-injection tools —
Wispr Flow and anything else that types by writing the clipboard and simulating
`Ctrl+V` — because the text never arrives and nothing reports an error.

If you use `^V` inside the terminal (vim's visual-block mode is the usual reason), turn
**Settings → General → Ctrl+V pastes in the terminal** off to restore it. `Ctrl+Alt+V`
sends a literal `^V` whether the setting is on or off, and `Ctrl+Shift+V` always pastes.

## Resizing

The terminal automatically resizes when you resize the browser window or drag the pane divider. The PTY dimensions update in real time so command output wraps correctly.

## Tmux Controls

Below the terminal, a toolbar provides quick access to tmux operations:

- **Window navigation** -- switch between tmux windows in the session
- **Copy mode** -- enter tmux copy mode for scrolling through output history
- **Page Up / Page Down** -- scroll through terminal output without entering full copy mode

## Send to Terminal

Other tabs (Todos, Prompts) include **Send to Terminal** buttons that inject text directly into the active terminal. This lets you fire off a prompt template or a todo item without copy-pasting.

## Notifications

A notification bell sound plays when the terminal emits a bell event (ASCII `\a`). This is useful for getting alerted when a long-running command finishes or when the AI needs your attention.
