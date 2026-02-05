"""
Main entry point for the DearPyGui interface.
"""
import dearpygui.dearpygui as dpg
from peg_this.ui.layout import setup_dpg
from peg_this.ui.state import UIState
from peg_this.ui.preview import player
from peg_this.utils.ffmpeg_utils import check_ffmpeg_ffprobe

def update_ui_from_state():
    """
    Called every frame. Syncs UI widgets with the global UIState.
    """
    state = UIState()
    
    # 1. Update Status Text
    if dpg.does_item_exist("txt_status"):
        current_text = dpg.get_value("txt_status")
        if current_text != state.job_status:
            dpg.set_value("txt_status", state.job_status)
            
            # Simple color coding
            color = (200, 200, 200) # Idle/Gray
            if state.job_status == "Running": color = (0, 255, 255) # Cyan
            elif state.job_status == "Completed": color = (0, 255, 0) # Green
            elif state.job_status == "Failed": color = (255, 0, 0) # Red
            
            dpg.configure_item("txt_status", color=color)

    # 2. Update Progress Bar
    if dpg.does_item_exist("progress_bar"):
        dpg.set_value("progress_bar", state.job_progress)

    # 3. Update File Selections
    if dpg.does_item_exist("status_input_file"):
        file_text = state.input_file if state.input_file else "No file selected"
        # Truncate if too long
        if len(file_text) > 50: file_text = "..." + file_text[-47:]
        dpg.set_value("status_input_file", file_text)

    if dpg.does_item_exist("status_output_dir"):
        dir_text = state.output_dir if state.output_dir else "Default (Same as input)"
        if len(dir_text) > 50: dir_text = "..." + dir_text[-47:]
        dpg.set_value("status_output_dir", dir_text)

    # 4. Stream Logs
    # (Logs are handled by sync_logs separately, but we could trigger it here if needed)

    # 5. Process Thread Queue (Callbacks)
    state.process_queue()

# Local log pointer to track what we've displayed
_last_log_count = 0

def sync_logs():
    global _last_log_count
    state = UIState()
    
    if not dpg.does_item_exist("log_text_widget"):
        return

    # Check if logs changed
    with state.queue_lock:
        current_count = len(state.job_logs)
        if current_count != _last_log_count:
            # Join all logs
            full_log_text = "\n".join(state.job_logs)
            dpg.set_value("log_text_widget", full_log_text)
            
            # Auto-scroll to bottom (approximate by setting scroll to a high value)
            # Input text doesn't support direct scroll control easily in DPG without internal flags,
            # but usually appending moves cursor. Since we replace, we might lose position.
            # DPG 1.0 workaround: set_y_scroll on the item might work if it's a child, but it's an input.
            # Actually, `configure_item` with `default_value` updates it.
            
            # For now, just updating content is enough to allow copying.
            _last_log_count = current_count

def run_gui():
    # Ensure FFmpeg is available
    check_ffmpeg_ffprobe()
    
    setup_dpg()
    
    # Primary Loop
    while dpg.is_dearpygui_running():
        update_ui_from_state()
        sync_logs()
        player.update()
        dpg.render_dearpygui_frame()
    
    dpg.destroy_context()
