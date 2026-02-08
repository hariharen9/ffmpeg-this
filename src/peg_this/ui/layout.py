"""
Defines the DearPyGui layout: Dockspace, Panels, and Widgets.
"""
import dearpygui.dearpygui as dpg
from peg_this.ui.state import UIState
from peg_this.ui.actions import (
    run_operation_threaded, 
    cancel_current_job, 
    handle_file_selection, 
    handle_dir_selection
)

def setup_fonts():
    # Placeholder for custom font loading if needed
    pass

def create_file_dialogs():
    # Input File Picker
    with dpg.file_dialog(directory_selector=False, show=False, callback=handle_file_selection, tag="file_dialog_input", width=700, height=400):
        dpg.add_file_extension(".*")
        dpg.add_file_extension(".mp4", color=(0, 255, 0, 255))
        dpg.add_file_extension(".mkv", color=(0, 255, 0, 255))
        dpg.add_file_extension(".mov", color=(0, 255, 0, 255))
        dpg.add_file_extension(".mp3", color=(255, 255, 0, 255))
        dpg.add_file_extension(".wav", color=(255, 255, 0, 255))
        dpg.add_file_extension(".jpg", color=(0, 255, 255, 255))
        dpg.add_file_extension(".png", color=(0, 255, 255, 255))

    # Output Directory Picker
    dpg.add_file_dialog(directory_selector=True, show=False, callback=handle_dir_selection, tag="dir_dialog_output", width=700, height=400)

def create_top_bar():
    with dpg.viewport_menu_bar():
        with dpg.group(horizontal=True):
            dpg.add_button(label="Select Input File", callback=lambda: dpg.show_item("file_dialog_input"))
            dpg.add_text("No file selected", tag="status_input_file")
            
            dpg.add_spacer(width=20)
            
            dpg.add_button(label="Output Dir", callback=lambda: dpg.show_item("dir_dialog_output"))
            dpg.add_text("Default (Same as input)", tag="status_output_dir")
            
            dpg.add_spacer(width=50)
            
            dpg.add_button(label="RUN", width=100, tag="btn_run", callback=lambda: run_operation_threaded(None, None))
            dpg.add_button(label="CANCEL", width=100, tag="btn_cancel", callback=cancel_current_job)

def refresh_operation_availability():
    """Enables or disables operation buttons based on the input file type."""
    from peg_this.ui.actions import is_operation_compatible
    state = UIState()
    if not state.input_file:
        return

    # List of all operations to check
    operations = [
        "To MP4", "Convert Format", "Compress", "GIF",
        "Trim", "Crop", "Split",
        "Extract Audio", "Remove Audio", "Volume", "Fade Audio", "Normalize Audio",
        "Speed", "Slow motion", "Reverse", "Rotate", "Flip", "Stabilize", "Fade Video", "Loop", "Color Correction", "Denoise", "Extract Frames", "PiP", "Watermark",
        "Subtitles (Whisper)", "Brainrot Captions", "Remove Background", "Blur Faces", "Music Separation", "Super Resolution",
        "Convert Format (Img)", "Resize", "Rotate (Img)", "Flip (Img)",
        "Audio Visualizer", "Inspect File", "Metadata", "Slideshow"
    ]

    for op in operations:
        tag = f"op_btn_{op.replace(' ', '_').replace('(', '').replace(')', '').lower()}"
        if not dpg.does_item_exist(tag):
            continue
            
        # We keep buttons enabled so they can be clicked to show the warning log
        # if the user tries to use an incompatible operation.
        dpg.configure_item(tag, enabled=True)

def on_operation_selected(sender, app_data, user_data):
    """Callback when an operation button is clicked."""
    from peg_this.ui.actions import is_operation_compatible
    state = UIState()
    
    if not is_operation_compatible(state.input_file, user_data):
        ext = state.input_file.split('.')[-1] if state.input_file else "None"
        state.add_log(f"Warning: '{user_data}' is not applicable for .{ext} files.")
        return

    state.selected_operation = user_data
    update_parameters_panel(user_data)

def update_parameters_panel(operation):
    """Rebuilds the Parameters panel based on the selected operation."""
    # Parent tag must match the window tag in init_layout
    parent = "win_parameters"
    
    # Clear existing controls
    dpg.delete_item(parent, children_only=True)
    
    # Header
    dpg.add_text(f"SETTINGS: {operation.upper()}", parent=parent, color=(0, 255, 255))
    dpg.add_separator(parent=parent)
    dpg.add_spacer(height=10, parent=parent)

    # --- Convert Group ---
    if operation == "To MP4" or operation == "Compress":
        dpg.add_text("CRF Quality (Lower is better):", parent=parent)
        dpg.add_slider_int(tag="param_crf", default_value=23, min_value=0, max_value=51, parent=parent)
        dpg.add_text("Preset:", parent=parent)
        dpg.add_combo(tag="param_preset", items=["ultrafast", "fast", "medium", "slow", "veryslow"], default_value="medium", parent=parent)

    elif operation == "Convert Format":
        dpg.add_text("Target Format:", parent=parent)
        dpg.add_combo(tag="param_format", items=["mp4", "mkv", "mov", "avi", "webm", "mp3", "wav", "flac"], default_value="mp4", parent=parent)

    elif operation == "GIF":
        dpg.add_text("Frame Rate:", parent=parent)
        dpg.add_input_int(tag="param_fps", default_value=15, parent=parent)
        dpg.add_text("Width (px):", parent=parent)
        dpg.add_input_int(tag="param_width", default_value=480, parent=parent)

    # --- Edit Group ---
    elif operation == "Trim":
        dpg.add_text("Start Time:", parent=parent)
        dpg.add_input_text(tag="param_trim_start", default_value="00:00:00", hint="HH:MM:SS or seconds", parent=parent)
        dpg.add_spacer(height=5, parent=parent)
        dpg.add_text("End Time:", parent=parent)
        dpg.add_input_text(tag="param_trim_end", default_value="", hint="HH:MM:SS or seconds", parent=parent)
        dpg.add_text("(Leave empty for end of video)", color=(150,150,150), parent=parent)

    elif operation == "Crop":
        dpg.add_text("Crop Geometry:", parent=parent)
        dpg.add_text("X:", parent=parent)
        dpg.add_input_int(tag="param_crop_x", default_value=0, parent=parent)
        dpg.add_text("Y:", parent=parent)
        dpg.add_input_int(tag="param_crop_y", default_value=0, parent=parent)
        dpg.add_text("Width:", parent=parent)
        dpg.add_input_int(tag="param_crop_w", default_value=1920, parent=parent)
        dpg.add_text("Height:", parent=parent)
        dpg.add_input_int(tag="param_crop_h", default_value=1080, parent=parent)
        dpg.add_text("(Visual crop tool coming soon, now you can use TUI for that)", color=(150,150,150), parent=parent)

    elif operation == "Split":
        dpg.add_text("Split Method:", parent=parent)
        dpg.add_combo(tag="param_split_method", items=["Equal Parts", "By Duration"], default_value="Equal Parts", parent=parent)
        dpg.add_text("Value (Parts count or Seconds):", parent=parent)
        dpg.add_input_int(tag="param_split_val", default_value=2, parent=parent)

    elif operation == "Join":
        dpg.add_text("Join Feature:", parent=parent)
        dpg.add_text("Currently requires manually selecting\nmultiple files in the input picker.\n(Implementation pending)", wrap=300, parent=parent)

    # --- Effects Group ---
    elif operation == "Speed":
        dpg.add_text("Speed Multiplier:", parent=parent)
        dpg.add_slider_float(tag="param_speed", default_value=1.0, min_value=0.25, max_value=4.0, parent=parent)
        dpg.add_text("(0.5 = Slow, 2.0 = Fast)", color=(150,150,150), parent=parent)

    elif operation == "Slow motion":
        dpg.add_text("Target Speed Multiplier:", parent=parent)
        dpg.add_slider_float(tag="param_of_speed", default_value=0.5, min_value=0.1, max_value=1.0, parent=parent)
        dpg.add_text("FPS (Output):", parent=parent)
        dpg.add_input_int(tag="param_of_fps", default_value=60, parent=parent)
        dpg.add_text("Processing Mode:", parent=parent)
        dpg.add_combo(tag="param_of_mode", items=["Balanced (Faster)", "High Quality (Slow)"], default_value="Balanced (Faster)", parent=parent)
        dpg.add_text("(Uses minterpolate for smooth slow-mo)", color=(150,150,150), parent=parent)

    elif operation == "PiP":
        dpg.add_text("Overlay Video File:", parent=parent)
        with dpg.group(horizontal=True, parent=parent):
            dpg.add_input_text(tag="param_pip_path", width=220)
            dpg.add_button(label="...", callback=lambda: dpg.show_item("file_dialog_input")) # Reuse dialog? Or new one.
        dpg.add_text("Position:", parent=parent)
        dpg.add_combo(tag="param_pip_pos", items=["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right", "Center"], default_value="Bottom-Right", parent=parent)
        dpg.add_text("Size (% of main):", parent=parent)
        dpg.add_slider_float(tag="param_pip_scale", default_value=0.25, min_value=0.1, max_value=0.5, parent=parent)

    elif operation == "Watermark":
        dpg.add_text("Watermark Type:", parent=parent)
        dpg.add_combo(tag="param_wm_type", items=["Image", "Text"], default_value="Image", parent=parent)
        
        # We'll use a conditional group or just show all
        dpg.add_text("Image Path / Text:", parent=parent)
        dpg.add_input_text(tag="param_wm_content", parent=parent)
        
        dpg.add_text("Position:", parent=parent)
        dpg.add_combo(tag="param_wm_pos", items=["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right", "Center"], default_value="Bottom-Right", parent=parent)
        dpg.add_text("Opacity (0.1 to 1.0):", parent=parent)
        dpg.add_slider_float(tag="param_wm_opacity", default_value=0.8, min_value=0.1, max_value=1.0, parent=parent)

    elif operation == "Reverse":
        dpg.add_text("Reverse Video + Audio", parent=parent)
        dpg.add_text("No parameters needed.", color=(150,150,150), parent=parent)

    elif operation == "Rotate":
        dpg.add_text("Rotation:", parent=parent)
        dpg.add_combo(tag="param_rotation", items=["90 Clockwise", "90 Counter-Clockwise", "180"], default_value="90 Clockwise", parent=parent)

    elif operation == "Flip":
        dpg.add_text("Direction:", parent=parent)
        dpg.add_combo(tag="param_flip_direction", items=["Horizontal", "Vertical"], default_value="Horizontal", parent=parent)

    elif operation == "Color Correction":
        dpg.add_text("Brightness (-1.0 to 1.0):", parent=parent)
        dpg.add_slider_float(tag="param_brightness", default_value=0.0, min_value=-1.0, max_value=1.0, parent=parent)
        dpg.add_text("Contrast (0.0 to 10.0):", parent=parent)
        dpg.add_slider_float(tag="param_contrast", default_value=1.0, min_value=0.0, max_value=10.0, parent=parent)
        dpg.add_text("Saturation (0.0 to 3.0):", parent=parent)
        dpg.add_slider_float(tag="param_saturation", default_value=1.0, min_value=0.0, max_value=3.0, parent=parent)

    elif operation == "Denoise":
        dpg.add_text("Luma Intensity:", parent=parent)
        dpg.add_slider_float(tag="param_denoise_luma", default_value=4.0, min_value=0.0, max_value=20.0, parent=parent)
        dpg.add_text("Chroma Intensity:", parent=parent)
        dpg.add_slider_float(tag="param_denoise_chroma", default_value=3.0, min_value=0.0, max_value=20.0, parent=parent)

    elif operation == "Fade Video":
        dpg.add_text("Fade In (sec):", parent=parent)
        dpg.add_input_float(tag="param_vfade_in", default_value=0.0, parent=parent)
        dpg.add_text("Fade Out (sec):", parent=parent)
        dpg.add_input_float(tag="param_vfade_out", default_value=0.0, parent=parent)

    elif operation == "Loop":
        dpg.add_text("Number of Loops:", parent=parent)
        dpg.add_input_int(tag="param_loop_count", default_value=2, min_value=-1, parent=parent)
        dpg.add_text("(-1 for infinite)", color=(150,150,150), parent=parent)

    elif operation == "Extract Frames":
        dpg.add_text("Interval (seconds):", parent=parent)
        dpg.add_input_float(tag="param_frame_interval", default_value=1.0, parent=parent)
        dpg.add_text("Format:", parent=parent)
        dpg.add_combo(tag="param_frame_fmt", items=["png", "jpg"], default_value="png", parent=parent)

    elif operation == "Stabilize":
        dpg.add_text("Shakiness (1-10):", parent=parent)
        dpg.add_slider_int(tag="param_shakiness", default_value=5, min_value=1, max_value=10, parent=parent)
        dpg.add_text("Smoothing (Frames):", parent=parent)
        dpg.add_slider_int(tag="param_smoothing", default_value=10, min_value=1, max_value=30, parent=parent)

    # --- Audio Group ---
    elif operation == "Volume":
        dpg.add_text("Volume Multiplier:", parent=parent)
        dpg.add_slider_float(tag="param_volume", default_value=1.0, min_value=0.0, max_value=4.0, parent=parent)
        dpg.add_text("(0.5 = 50%, 2.0 = 200%)", color=(150,150,150), parent=parent)

    elif operation == "Fade Audio":
        dpg.add_text("Fade In (sec):", parent=parent)
        dpg.add_input_float(tag="param_afade_in", default_value=0.0, parent=parent)
        dpg.add_text("Fade Out (sec):", parent=parent)
        dpg.add_input_float(tag="param_afade_out", default_value=0.0, parent=parent)

    elif operation == "Normalize Audio":
        dpg.add_text("Method:", parent=parent)
        dpg.add_combo(tag="param_norm_method", items=["EBU R128", "Peak", "RMS", "Dynamic"], default_value="EBU R128", parent=parent)

    elif operation == "Extract Audio":
        dpg.add_text("Format:", parent=parent)
        dpg.add_combo(tag="param_extract_fmt", items=["mp3", "flac", "wav"], default_value="mp3", parent=parent)

    elif operation == "Remove Audio":
        dpg.add_text("Removes audio track.", parent=parent)

    # --- AI Tools Group ---
    elif operation == "Subtitles (Whisper)":
        dpg.add_text("Model Size:", parent=parent)
        dpg.add_combo(tag="param_whisper_model", items=["tiny", "base", "small", "medium", "large-v3"], default_value="base", parent=parent)
        dpg.add_text("Output Mode:", parent=parent)
        dpg.add_combo(tag="param_sub_mode", items=["Sidecar (.srt)", "Embed (Soft)", "Burn-in (Hard)"], default_value="Sidecar (.srt)", parent=parent)
        dpg.add_text("Language (Optional):", parent=parent)
        dpg.add_input_text(tag="param_lang", hint="e.g. en, fr, auto", default_value="auto", parent=parent)

    elif operation == "AI Auto-Dubbing":
        from peg_this.features.dubbing import LANGUAGES
        dpg.add_text("Target Language:", parent=parent)
        dpg.add_combo(tag="param_dub_lang", items=list(LANGUAGES.keys()), default_value="Spanish", parent=parent)
        dpg.add_text("Model Size:", parent=parent)
        dpg.add_combo(tag="param_whisper_model", items=["tiny", "base", "small"], default_value="base", parent=parent)

    elif operation == "Brainrot Captions":
        dpg.add_text("Style:", parent=parent)
        dpg.add_combo(tag="param_brainrot_style", items=["Classic", "Highlighted", "Colorful", "Neon", "Bold"], default_value="Classic", parent=parent)
        dpg.add_text("Model:", parent=parent)
        dpg.add_combo(tag="param_whisper_model", items=["tiny", "base", "small"], default_value="base", parent=parent)

    elif operation == "Remove Background":
        dpg.add_text("Background Type:", parent=parent)
        dpg.add_combo(tag="param_bg_type", items=["Transparent (WebM/PNG)", "Green Screen", "Solid Color (Black)", "Solid Color (White)"], default_value="Transparent (WebM/PNG)", parent=parent)
        dpg.add_text("(Now supports both Images and Videos)", color=(0, 255, 0), parent=parent)

    elif operation == "Blur Faces":
        dpg.add_text("Detection Method:", parent=parent)
        dpg.add_combo(tag="param_blur_method", items=["MediaPipe AI (Accurate)", "OpenCV Haar (Fast)"], default_value="MediaPipe AI (Accurate)", parent=parent)
        dpg.add_text("Sensitivity:", parent=parent)
        dpg.add_combo(tag="param_blur_sense", items=["High", "Medium", "Low"], default_value="Medium", parent=parent)
        dpg.add_text("Blur Strength:", parent=parent)
        dpg.add_combo(tag="param_blur_strength", items=["Light", "Medium", "Heavy", "Pixelate"], default_value="Medium", parent=parent)
        dpg.add_text("Padding (%):", parent=parent)
        dpg.add_slider_float(tag="param_blur_pad", default_value=0.2, min_value=0.0, max_value=0.5, parent=parent)

    elif operation == "Music Separation":
        dpg.add_text("Stems to Extract:", parent=parent)
        dpg.add_combo(tag="param_stems", items=["2 (Vocals/Other)", "4 (Vocals/Drums/Bass/Other)", "6 (Advanced)"], default_value="2 (Vocals/Other)", parent=parent)
        dpg.add_text("Output Format:", parent=parent)
        dpg.add_combo(tag="param_stem_fmt", items=["mp3", "flac", "wav"], default_value="mp3", parent=parent)

    elif operation == "Super Resolution":
        dpg.add_text("Mode:", parent=parent)
        dpg.add_combo(tag="param_upscale_mode", items=["Quick (FFmpeg)", "Fast AI", "Quality AI", "Anime AI"], default_value="Fast AI", parent=parent)
        dpg.add_text("Scale Factor:", parent=parent)
        dpg.add_combo(tag="param_upscale_factor", items=["2x", "4x"], default_value="2x", parent=parent)
        dpg.add_text("AI Model:", parent=parent)
        dpg.add_combo(tag="param_upscale_model", items=[
            "RealESRGAN_x2plus (2x Native - Fastest)",
            "realesr-general-x4v3 (4x Fast)",
            "realesr-general-wdn-x4v3 (4x Fast + Denoise)",
            "RealESRGAN_x4plus (4x Best Quality)",
            "RealESRNet_x4plus (4x Balanced)",
            "realesr-animevideov3 (Anime Fast)",
            "RealESRGAN_x4plus_anime_6B (Anime Quality)"
        ], default_value="RealESRGAN_x2plus (2x Native - Fastest)", parent=parent)
        dpg.add_text("Memory/Tile Size:", parent=parent)
        dpg.add_combo(tag="param_upscale_tile", items=["Auto (Recommended)", "No Tiling (Fast)", "512", "256", "128"], default_value="Auto (Recommended)", parent=parent)
        dpg.add_text("FFmpeg Algorithm:", parent=parent)
        dpg.add_combo(tag="param_upscale_algo", items=["lanczos", "bicubic", "bilinear", "spline"], default_value="lanczos", parent=parent)
        dpg.add_text("(2x scale + RealESRGAN_x2plus = fastest AI)", color=(100, 200, 100), parent=parent)

    # --- Other Group ---
    elif operation == "Audio Visualizer":
        dpg.add_text("Style:", parent=parent)
        dpg.add_combo(tag="param_viz_style", items=["Spectrum Bars", "Waveform", "CQT", "Spectrogram"], default_value="Spectrum Bars", parent=parent)
        dpg.add_text("Resolution:", parent=parent)
        dpg.add_combo(tag="param_viz_res", items=["1920x1080", "1280x720", "1080x1920"], default_value="1920x1080", parent=parent)

    elif operation == "Inspect File":
        dpg.add_text("Click RUN to analyze file metadata.", parent=parent)

    elif operation == "Metadata":
        dpg.add_text("Edit Metadata:", parent=parent)
        dpg.add_input_text(tag="param_meta_title", label="Title", parent=parent)
        dpg.add_input_text(tag="param_meta_artist", label="Artist", parent=parent)
        dpg.add_input_text(tag="param_meta_album", label="Album", parent=parent)
        dpg.add_input_text(tag="param_meta_year", label="Year", parent=parent)
        dpg.add_input_text(tag="param_meta_comment", label="Comment", parent=parent)

    # --- Image Group ---
    elif operation == "Resize":
        dpg.add_text("Width (-1 for auto):", parent=parent)
        dpg.add_input_int(tag="param_width", default_value=1280, step=0, parent=parent) 
        dpg.add_text("Height (-1 for auto):", parent=parent)
        dpg.add_input_int(tag="param_height", default_value=-1, step=0, parent=parent)

    elif operation == "Convert Format (Img)":
        dpg.add_text("Target Format:", parent=parent)
        dpg.add_combo(tag="param_img_format", items=["png", "jpg", "webp"], default_value="png", parent=parent)

    elif operation == "Rotate (Img)":
        dpg.add_text("Angle:", parent=parent)
        dpg.add_combo(tag="param_img_rotate", items=["90 Clockwise", "90 Counter-Clockwise", "180"], default_value="90 Clockwise", parent=parent)

    elif operation == "Flip (Img)":
        dpg.add_text("Direction:", parent=parent)
        dpg.add_combo(tag="param_img_flip", items=["Horizontal", "Vertical"], default_value="Horizontal", parent=parent)

    else:
        dpg.add_text("No parameters needed or\nnot implemented yet.", parent=parent)

def create_operations_panel():
    # Helper to creating expandable categories
    def add_category(label, items):
        with dpg.collapsing_header(label=label, default_open=True):
            for item in items:
                # Predictive tag for dynamic control
                tag = f"op_btn_{item.replace(' ', '_').replace('(', '').replace(')', '').lower()}"
                dpg.add_button(label=item, width=-1, callback=on_operation_selected, user_data=item, tag=tag)

    add_category("Convert", ["To MP4", "Convert Format", "Compress", "GIF"])
    add_category("Edit", ["Trim", "Crop", "Split"])
    add_category("Audio", ["Extract Audio", "Remove Audio", "Volume", "Fade Audio", "Normalize Audio"])
    add_category("Effects", ["Speed", "Slow motion", "Reverse", "Rotate", "Flip", "Stabilize", "Fade Video", "Loop", "Color Correction", "Denoise", "Extract Frames", "PiP", "Watermark"])
    add_category("AI Tools", ["Subtitles (Whisper)", "AI Auto-Dubbing", "Brainrot Captions", "Remove Background", "Blur Faces", "Music Separation", "Super Resolution"])
    add_category("Image", ["Convert Format (Img)", "Resize", "Rotate (Img)", "Flip (Img)"])
    add_category("Other", ["Audio Visualizer", "Inspect File", "Metadata", "Slideshow"])

from peg_this.ui.preview import player

def create_preview_panel():
    with dpg.group(horizontal=True):
        dpg.add_text("PREVIEW", color=(0, 255, 0))
        dpg.add_spacer(width=20)
        dpg.add_text("00:00 / 00:00", tag="preview_time_text", color=(150, 150, 150))

    dpg.add_separator()
    
    # Video Area (Texture)
    # Using drawlist for explicit control
    with dpg.group(horizontal=True):
        dpg.add_spacer(width=0)
        # Canvas size 600x400
        with dpg.drawlist(width=600, height=400):
            dpg.draw_image("video_texture", pmin=(0, 0), pmax=(600, 400))

    dpg.add_spacer(height=5)

    # Controls
    # Seek Slider
    # We set max_value dynamically when file loads
    dpg.add_slider_int(tag="preview_seek_slider", width=-1, default_value=0, max_value=100, callback=lambda s, a: player.seek(a))

    with dpg.group(horizontal=True):
        dpg.add_button(label="Play/Pause", width=100, callback=lambda: player.toggle_play())
        
        dpg.add_text("Speed:")
        dpg.add_combo(items=["0.5x", "1.0x", "1.5x", "2.0x"], default_value="1.0x", width=80, 
                      callback=lambda s, a: setattr(player, 'speed', float(a.replace('x', ''))))
        
        dpg.add_spacer(width=20)
        dpg.add_checkbox(label="Show Subtitles", default_value=True, callback=lambda s, a: setattr(player, 'show_subtitles', a))
        
        dpg.add_spacer(width=20)
        dpg.add_button(label="Clear", callback=lambda: player.unload())
        
        dpg.add_spacer(width=20)
        # Volume (Visual only for now)
        dpg.add_text("Vol:")
        dpg.add_slider_float(default_value=1.0, max_value=1.0, width=100, callback=lambda: print("Volume not supported in preview yet"))

def create_parameters_panel():
    # Initial placeholder content
    dpg.add_text("Select an operation from the left panel.", color=(150, 150, 150))

def create_bottom_panel():
    with dpg.group(horizontal=True):
        dpg.add_text("Status:")
        dpg.add_text("Idle", tag="txt_status", color=(200, 200, 200))
    
    dpg.add_progress_bar(label="Progress", tag="progress_bar", width=-1, default_value=0.0)
    dpg.add_separator()
    
    # Use Input Text for copyable logs
    dpg.add_input_text(tag="log_text_widget", multiline=True, readonly=True, width=-1, height=-1)

def init_layout():
    # Setup Dialogs (Hidden)
    create_file_dialogs()

    # Top Bar (Menu Bar)
    create_top_bar()

    # Define Independent Windows (Floating/Dockable)
    
    with dpg.window(label="Operations", width=250, height=770, pos=(0, 30), no_close=True):
        create_operations_panel()
    
    with dpg.window(label="Preview", width=600, height=400, pos=(260, 30), no_close=True):
        create_preview_panel()
    
    # Tag added here for targeting updates
    with dpg.window(label="Parameters", tag="win_parameters", width=300, height=400, pos=(870, 30), no_close=True):
        create_parameters_panel()
        
    with dpg.window(label="Logs & Progress", width=910, height=330, pos=(260, 440), no_close=True):
        create_bottom_panel()

    # Overwrite Confirmation Modal
    with dpg.window(label="Confirm Overwrite", modal=True, show=False, tag="modal_overwrite", width=300, height=150, pos=(400, 300), no_move=True):
        dpg.add_text("File exists. Overwrite?", tag="txt_overwrite_msg")
        dpg.add_spacer(height=20)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Yes, Overwrite", tag="btn_overwrite_yes", width=120)
            dpg.add_button(label="Cancel", tag="btn_overwrite_no", width=120, callback=lambda: dpg.configure_item("modal_overwrite", show=False))

def setup_dpg():
    dpg.create_context()
    
    # Create Texture Registry and Dynamic Texture
    import numpy as np
    # Initialize with Opaque Black
    # Shape: 400x600, 4 channels (RGBA)
    black_frame = np.zeros((400, 600, 4), dtype=np.float32)
    black_frame[:, :, 3] = 1.0 # Alpha = 1.0
    
    with dpg.texture_registry(show=False):
        dpg.add_dynamic_texture(width=600, height=400, default_value=black_frame.flatten(), tag="video_texture")

    # Enable Docking
    dpg.configure_app(docking=True, docking_space=True)
    
    # Setup viewport before creating windows to ensure font scaling/DPI might be handled if we added that
    dpg.create_viewport(title="FFmpeg-This Studio", width=1280, height=800)
    
    init_layout()
    
    dpg.setup_dearpygui()
    dpg.show_viewport()