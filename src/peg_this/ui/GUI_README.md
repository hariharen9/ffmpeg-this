# FFmpeg-This GUI Module

This module implements the optional DearPyGui-based graphical interface for `ffmpeg-this`.

## Architecture

*   **`app.py`**: Main entry point (`run_gui`). Handles the DPG render loop and UI updates.
*   **`layout.py`**: Defines the widget hierarchy, windows, dockspace, and panels.
*   **`state.py`**: Singleton `UIState` class that holds application state (selected files, job progress, logs) in a thread-safe manner.
*   **`actions.py`**: The "Controller". Bridges UI events (buttons, file picks) to logic. Handles background threading for long-running tasks.

## Design Principles

1.  **Isolation**: The GUI code does not import `peg_this` core features unless necessary, and avoids modifying core files.
2.  **Threading**: All FFmpeg operations run in background threads (`actions.run_operation_threaded`) to keep the UI responsive.
3.  **Log Redirection**: `stdout` and `stderr` are captured during operations and streamed to the "Logs" panel.
4.  **Dynamic Parameters**: The "Parameters" panel is rebuilt on-the-fly based on the selected operation.

## Adding a New Feature

1.  **Update `layout.py`**: Add the operation button to `create_operations_panel`.
2.  **Update `layout.py`**: Add parameter widgets for the new operation in `update_parameters_panel`.
3.  **Update `actions.py`**: 
    *   Add parameter collection logic in `collect_parameters`.
    *   Implement a `_do_FEATURE` function that constructs the FFmpeg command.
    *   Add dispatch logic in `run_operation_threaded`.
