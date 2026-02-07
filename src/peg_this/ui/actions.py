"""
Bridge between UI actions and core business logic.
Handles threading, state updates, and mapping UI events to feature functions.
"""
import threading
import sys
import io
import time
import os
import shutil
import tempfile
import json
import re
import logging
from pathlib import Path
from typing import Callable

import dearpygui.dearpygui as dpg
import ffmpeg

from peg_this.ui.state import UIState
from peg_this.ui.preview import player
from peg_this.utils.ffmpeg_utils import run_command
from peg_this.utils.validation import validate_time_input, get_video_duration
from peg_this.features.dubbing import LANGUAGES
from peg_this.features.subtitle import extract_audio_for_whisper

class UILogHandler(logging.Handler):
    """Redirects logs to the UI state."""
    def __init__(self, ui_state: UIState):
        super().__init__()
        self.ui_state = ui_state
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def emit(self, record):
        try:
            msg = self.format(record)
            clean_msg = self.ansi_escape.sub('', msg)
            self.ui_state.add_log(clean_msg)
        except Exception:
            self.handleError(record)

# --- File Selection Handlers ---

def handle_file_selection(sender, app_data, user_data):
    """Callback for Input File Picker."""
    from peg_this.ui.layout import refresh_operation_availability
    state = UIState()
    if 'selections' in app_data and app_data['selections']:
        first_selection = list(app_data['selections'].values())[0]
        state.input_file = first_selection
        state.add_log(f"Selected Input: {first_selection}")
        player.load_file(first_selection)
        refresh_operation_availability()
    elif 'file_path_name' in app_data:
        selected_path = app_data['file_path_name']
        if not selected_path.endswith(".*"):
            state.input_file = selected_path
            state.add_log(f"Selected Input: {selected_path}")
            player.load_file(selected_path)
            refresh_operation_availability()

def handle_dir_selection(sender, app_data, user_data):
    """Callback for Output Directory Picker."""
    state = UIState()
    if 'file_path_name' in app_data:
        selected_path = app_data['file_path_name']
        state.output_dir = selected_path
        state.add_log(f"Selected Output Dir: {selected_path}")

# --- Helper Logic ---

def get_output_path(input_path, suffix, ext=None):
    state = UIState()
    p = Path(input_path)
    extension = ext if ext else p.suffix
    filename = f"{p.stem}_{suffix}{extension}"
    
    out_path = str(p.with_name(filename))
    if state.output_dir:
        out_path = os.path.join(state.output_dir, filename)
    
    state.last_generated_file = out_path
    return out_path

def collect_parameters(operation):
    """Reads values from DPG widgets based on the operation."""
    params = {}
    try:
        if operation == "Trim":
            params['start'] = dpg.get_value("param_trim_start")
            params['end'] = dpg.get_value("param_trim_end")
        elif operation == "Convert Format":
            params['format'] = dpg.get_value("param_format")
        elif operation == "Compress":
            params['crf'] = dpg.get_value("param_crf")
            params['preset'] = dpg.get_value("param_preset")
        elif operation == "GIF":
            params['fps'] = dpg.get_value("param_fps")
            params['width'] = dpg.get_value("param_width")
        elif operation == "Crop":
            params['x'] = dpg.get_value("param_crop_x")
            params['y'] = dpg.get_value("param_crop_y")
            params['w'] = dpg.get_value("param_crop_w")
            params['h'] = dpg.get_value("param_crop_h")
        elif operation == "Speed":
            params['speed'] = dpg.get_value("param_speed")
        elif operation == "Slow motion":
            params['speed'] = dpg.get_value("param_of_speed")
            params['fps'] = dpg.get_value("param_of_fps")
            params['mode'] = dpg.get_value("param_of_mode")
        elif operation == "PiP":
            params['overlay'] = dpg.get_value("param_pip_path")
            params['pos'] = dpg.get_value("param_pip_pos")
            params['scale'] = dpg.get_value("param_pip_scale")
        elif operation == "Watermark":
            params['type'] = dpg.get_value("param_wm_type")
            params['content'] = dpg.get_value("param_wm_content")
            params['pos'] = dpg.get_value("param_wm_pos")
            params['opacity'] = dpg.get_value("param_wm_opacity")
        elif operation == "Rotate":
            params['rotation'] = dpg.get_value("param_rotation")
        elif operation == "Flip":
            params['direction'] = dpg.get_value("param_flip_direction")
        elif operation == "Stabilize":
            params['shakiness'] = dpg.get_value("param_shakiness")
            params['smoothing'] = dpg.get_value("param_smoothing")
        elif operation == "Subtitles (Whisper)":
            params['model'] = dpg.get_value("param_whisper_model")
            params['mode'] = dpg.get_value("param_sub_mode")
            params['lang'] = dpg.get_value("param_lang")
        elif operation == "AI Auto-Dubbing":
            params['lang'] = dpg.get_value("param_dub_lang")
            params['model'] = dpg.get_value("param_whisper_model")
        elif operation == "Remove Background":
            params['type'] = dpg.get_value("param_bg_type")
        elif operation == "Blur Faces":
            params['method'] = dpg.get_value("param_blur_method")
            params['sensitivity'] = dpg.get_value("param_blur_sense")
            params['strength'] = dpg.get_value("param_blur_strength")
            params['padding'] = dpg.get_value("param_blur_pad")
        elif operation == "Music Separation":
            params['stems'] = dpg.get_value("param_stems")
            params['fmt'] = dpg.get_value("param_stem_fmt")
        elif operation == "Extract Frames":
            params['interval'] = dpg.get_value("param_frame_interval")
            params['fmt'] = dpg.get_value("param_frame_fmt")
        elif operation == "Color Correction":
            params['brightness'] = dpg.get_value("param_brightness")
            params['contrast'] = dpg.get_value("param_contrast")
            params['saturation'] = dpg.get_value("param_saturation")
        elif operation == "Denoise":
            params['luma'] = dpg.get_value("param_denoise_luma")
            params['chroma'] = dpg.get_value("param_denoise_chroma")
        elif operation == "Fade Video":
            params['in'] = dpg.get_value("param_vfade_in")
            params['out'] = dpg.get_value("param_vfade_out")
        elif operation == "Loop":
            params['count'] = dpg.get_value("param_loop_count")
        elif operation == "Convert Format (Img)":
            params['format'] = dpg.get_value("param_img_format")
        elif operation == "Rotate (Img)":
            params['rotation'] = dpg.get_value("param_img_rotate")
        elif operation == "Flip (Img)":
            params['direction'] = dpg.get_value("param_img_flip")
        elif operation == "Resize":
            params['width'] = dpg.get_value("param_width")
            params['height'] = dpg.get_value("param_height")
        elif operation == "Volume":
            params['vol'] = dpg.get_value("param_volume")
        elif operation == "Fade Audio":
            params['in'] = dpg.get_value("param_afade_in")
            params['out'] = dpg.get_value("param_afade_out")
        elif operation == "Normalize Audio":
            params['method'] = dpg.get_value("param_norm_method")
        elif operation == "Extract Audio":
            params['fmt'] = dpg.get_value("param_extract_fmt")
        elif operation == "Split":
            params['method'] = dpg.get_value("param_split_method")
            params['val'] = dpg.get_value("param_split_val")
        elif operation == "Brainrot Captions":
            params['style'] = dpg.get_value("param_brainrot_style")
            params['model'] = dpg.get_value("param_whisper_model")
        elif operation == "Audio Visualizer":
            params['style'] = dpg.get_value("param_viz_style")
            params['res'] = dpg.get_value("param_viz_res")
        elif operation == "Metadata":
            params['title'] = dpg.get_value("param_meta_title")
            params['artist'] = dpg.get_value("param_meta_artist")
            params['album'] = dpg.get_value("param_meta_album")
            params['year'] = dpg.get_value("param_meta_year")
            params['comment'] = dpg.get_value("param_meta_comment")
        elif operation == "Slideshow":
            # Slideshow defaults
            params['duration'] = 3.0
            
    except Exception:
        pass # Widget might not exist if panel wasn't updated
    
    return params

# --- Feature Implementations ---

def is_operation_compatible(file_path, operation):
    """Returns True if the operation is compatible with the file extension."""
    if not file_path or not operation:
        return True # Default to true to avoid blocking if no file yet
        
    ext = file_path.lower().split('.')[-1]
    is_video = ext in ["mp4", "mkv", "mov", "avi", "webm", "flv", "wmv"]
    is_audio = ext in ["mp3", "wav", "flac", "ogg", "m4a", "aac"]
    is_image = ext in ["jpg", "jpeg", "png", "webp", "bmp", "tiff"]

    # Mapping: Operation -> List of compatible types
    compatibility = {
        "To MP4": ["video"],
        "Convert Format": ["video", "audio"],
        "Compress": ["video"],
        "GIF": ["video"],
        "Trim": ["video", "audio"],
        "Crop": ["video"],
        "Split": ["video", "audio"],
        "Extract Audio": ["video"],
        "Remove Audio": ["video"],
        "Volume": ["video", "audio"],
        "Fade Audio": ["video", "audio"],
        "Normalize Audio": ["video", "audio"],
        "Speed": ["video", "audio"],
        "Slow motion": ["video"],
        "Reverse": ["video", "audio"],
        "Rotate": ["video"],
        "Flip": ["video"],
        "Stabilize": ["video"],
        "Fade Video": ["video"],
        "Loop": ["video", "audio"],
        "Color Correction": ["video"],
        "Denoise": ["video"],
        "Extract Frames": ["video"],
        "PiP": ["video"],
        "Watermark": ["video"],
        "Subtitles (Whisper)": ["video", "audio"],
        "AI Auto-Dubbing": ["video"],
        "Brainrot Captions": ["video"],
        "Remove Background": ["video", "image"],
        "Blur Faces": ["video"],
        "Music Separation": ["video", "audio"],
        "Convert Format (Img)": ["image"],
        "Resize": ["image"],
        "Rotate (Img)": ["image"],
        "Flip (Img)": ["image"],
        "Audio Visualizer": ["video", "audio"],
        "Inspect File": ["video", "audio", "image"],
        "Metadata": ["video", "audio", "image"],
        "Slideshow": ["video", "audio", "image"]
    }

    allowed = compatibility.get(operation, ["video", "audio", "image"])
    if is_video and "video" in allowed: return True
    if is_audio and "audio" in allowed: return True
    if is_image and "image" in allowed: return True
    return False

def confirm_overwrite(state, path):
    """
    Checks if path exists. If so, asks user via GUI modal (blocking the thread).
    Returns True if safe to proceed (overwrite or new file), False if cancelled.
    """
    if not os.path.exists(path):
        return True
        
    event = threading.Event()
    result = {'overwrite': False}
    
    def on_yes(sender, app_data):
        result['overwrite'] = True
        dpg.configure_item("modal_overwrite", show=False)
        event.set()
        
    def on_no(sender, app_data):
        result['overwrite'] = False
        dpg.configure_item("modal_overwrite", show=False)
        event.set()
        
    def show_modal():
        dpg.set_value("txt_overwrite_msg", f"File already exists:\n{os.path.basename(path)}\n\nOverwrite it?")
        dpg.set_item_callback("btn_overwrite_yes", on_yes)
        dpg.set_item_callback("btn_overwrite_no", on_no)
        dpg.configure_item("modal_overwrite", show=True)
        
    state.queue_callback(show_modal)
    state.add_log(f"Waiting for overwrite confirmation: {os.path.basename(path)}")
    event.wait()
    
    if not result['overwrite']:
        state.add_log("Operation cancelled by user.")
        
    return result['overwrite']

def _do_trim(state, params):
    start_str = params.get('start', '0')
    end_str = params.get('end', '')
    duration = get_video_duration(state.input_file)
    start_sec = validate_time_input(start_str, duration)
    end_sec = validate_time_input(end_str, duration) if end_str.strip() else None
    
    if start_sec is None: return

    output_path = get_output_path(state.input_file, "trimmed")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Trimming... Output: {output_path}")

    input_stream = ffmpeg.input(state.input_file)
    kwargs = {'c:v': 'libx264', 'crf': 23, 'c:a': 'aac'}
    if end_sec:
        stream = ffmpeg.output(input_stream, output_path, ss=start_sec, to=end_sec, **kwargs).overwrite_output()
    else:
        stream = ffmpeg.output(input_stream, output_path, ss=start_sec, **kwargs).overwrite_output()

    run_command(stream, description="Trimming...", show_progress=True)

def _do_convert(state, params):
    fmt = params.get('format', 'mp4')
    output_path = get_output_path(state.input_file, "converted", f".{fmt}")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Converting to {fmt}...")
    
    # We do NOT use -c copy here to ensure safety for format changes (mp4 -> webm, etc.)
    # FFmpeg will auto-select the right codec for the container.
    stream = ffmpeg.input(state.input_file).output(output_path).overwrite_output()
    success = run_command(stream, description="Converting...", show_progress=True)
    if success: state.add_log("Conversion successful!")
    else: state.add_log("Conversion failed.")

def _do_compress(state, params):
    crf = params.get('crf', 23)
    preset = params.get('preset', 'medium')
    output_path = get_output_path(state.input_file, "compressed")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Compressing (CRF {crf}, Preset {preset})...")
    
    stream = ffmpeg.input(state.input_file).output(output_path, vcodec='libx264', crf=crf, preset=preset, acodec='aac').overwrite_output()
    run_command(stream, description="Compressing...", show_progress=True)

def _do_gif(state, params):
    fps = params.get('fps', 15)
    width = params.get('width', 480)
    output_path = get_output_path(state.input_file, "animated", ".gif")
    if not confirm_overwrite(state, output_path): return
    palette_path = os.path.join(tempfile.gettempdir(), "palette.png")
    
    state.add_log("Generating GIF palette...")
    try:
        (
            ffmpeg.input(state.input_file)
            .filter('fps', fps=fps)
            .filter('scale', width, -1, flags='lanczos')
            .filter('palettegen')
            .output(palette_path, y=None)
            .overwrite_output()
            .run(quiet=True)
        )
        
        state.add_log("Creating GIF...")
        input_stream = ffmpeg.input(state.input_file)
        palette_stream = ffmpeg.input(palette_path)
        
        v_stream = input_stream.filter('fps', fps=fps).filter('scale', width, -1, flags='lanczos')
        
        stream = ffmpeg.filter([v_stream, palette_stream], 'paletteuse').output(output_path).overwrite_output()
        run_command(stream, description="GIF", show_progress=True)
        
    finally:
        if os.path.exists(palette_path):
            os.remove(palette_path)

def _do_speed(state, params):
    speed = params.get('speed', 1.0)
    output_path = get_output_path(state.input_file, f"speed_{speed}x")
    if not confirm_overwrite(state, output_path): return
    
    pts_mult = 1.0 / speed
    state.add_log(f"Applying Speed {speed}x...")
    
    input_stream = ffmpeg.input(state.input_file)
    v = input_stream.video.filter('setpts', f'{pts_mult}*PTS')
    a = input_stream.audio.filter('atempo', speed)
    
    stream = ffmpeg.output(v, a, output_path).overwrite_output()
    run_command(stream, description="Speed Change", show_progress=True)

def _do_optical_flow(state, params):
    speed = params.get('speed', 0.5)
    fps = params.get('fps', 60)
    mode = params.get('mode', 'Balanced (Faster)')
    output_path = get_output_path(state.input_file, f"slowmo_flow")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Applying Optical Flow Slow-mo ({mode}): Speed={speed}, Target FPS={fps}")
    
    # Balanced mode uses 'obmc' (Overlapped Block Motion Compensation) which is faster than 'aobmc'
    # and slightly less aggressive motion estimation.
    mc_mode = 'obmc' if "Balanced" in mode else 'aobmc'
    me_mode = 'bilat' if "Balanced" in mode else 'bidir' # Bilateral is generally faster
    
    v = (
        ffmpeg.input(state.input_file).video
        .filter('setpts', f'{1.0/speed}*PTS')
        .filter('minterpolate', fps=fps, mi_mode='mci', mc_mode=mc_mode, me_mode=me_mode)
    )
    # Handle audio if exists
    input_stream = ffmpeg.input(state.input_file)
    try:
        a = input_stream.audio.filter('atempo', speed)
        stream = ffmpeg.output(v, a, output_path).overwrite_output()
    except:
        stream = ffmpeg.output(v, output_path).overwrite_output()
        
    run_command(stream, description="Optical Flow (Slow)", show_progress=True)

def _do_pip(state, params):
    overlay_path = params.get('overlay', '')
    pos = params.get('pos', 'Bottom-Right')
    scale = params.get('scale', 0.25)
    
    if not overlay_path or not os.path.exists(overlay_path):
        state.add_log("Error: Overlay file not found.")
        return
        
    output_path = get_output_path(state.input_file, "pip")
    if not confirm_overwrite(state, output_path): return
    
    padding = 20
    pos_map = {
        "Top-Left": (str(padding), str(padding)),
        "Top-Right": (f"main_w-overlay_w-{padding}", str(padding)),
        "Bottom-Left": (str(padding), f"main_h-overlay_h-{padding}"),
        "Bottom-Right": (f"main_w-overlay_w-{padding}", f"main_h-overlay_h-{padding}"),
        "Center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2")
    }
    x_pos, y_pos = pos_map.get(pos, pos_map["Bottom-Right"])
    
    state.add_log(f"Creating PiP with {os.path.basename(overlay_path)}...")
    main = ffmpeg.input(state.input_file)
    overlay = ffmpeg.input(overlay_path).video.filter('scale', f"iw*{scale}", f"ih*{scale}")
    
    v = ffmpeg.overlay(main.video, overlay, x=x_pos, y=y_pos, shortest=1)
    stream = ffmpeg.output(v, main.audio, output_path).overwrite_output()
    run_command(stream, description="PiP", show_progress=True)

def _do_watermark(state, params):
    wm_type = params.get('type', 'Image')
    content = params.get('content', '')
    pos = params.get('pos', 'Bottom-Right')
    opacity = params.get('opacity', 0.8)
    
    output_path = get_output_path(state.input_file, "watermarked")
    if not confirm_overwrite(state, output_path): return
    
    padding = 20
    pos_map = {
        "Top-Left": (f"{padding}", f"{padding}"),
        "Top-Right": (f"W-w-{padding}", f"{padding}"),
        "Bottom-Left": (f"{padding}", f"H-h-{padding}"),
        "Bottom-Right": (f"W-w-{padding}", f"H-h-{padding}"),
        "Center": ("(W-w)/2", "(H-h)/2")
    }
    x_pos, y_pos = pos_map.get(pos, pos_map["Bottom-Right"])
    
    main = ffmpeg.input(state.input_file)
    
    if wm_type == "Image":
        if not content or not os.path.exists(content):
            state.add_log("Error: Watermark image not found.")
            return
        state.add_log(f"Applying Image Watermark: {os.path.basename(content)}")
        wm = ffmpeg.input(content).filter('colorchannelmixer', aa=opacity)
        v = ffmpeg.overlay(main.video, wm, x=x_pos, y=y_pos)
    else:
        state.add_log(f"Applying Text Watermark: '{content}'")
        # Map pos for drawtext
        dt_pos = {
            "Top-Left": f"x={padding}:y={padding}",
            "Top-Right": f"x=w-tw-{padding}:y={padding}",
            "Bottom-Left": f"x={padding}:y=h-th-{padding}",
            "Bottom-Right": f"x=w-tw-{padding}:y=h-th-{padding}",
            "Center": f"x=(w-tw)/2:y=(h-th)/2"
        }.get(pos, f"x=w-tw-{padding}:y=h-th-{padding}")
        
        x_dt, y_dt = dt_pos.split(':')
        v = main.video.filter('drawtext', text=content, fontsize=24, fontcolor=f'white@{opacity}', 
                              borderw=1, bordercolor='black', 
                              **{x_dt.split('=')[0]: x_dt.split('=')[1], 
                                 y_dt.split('=')[0]: y_dt.split('=')[1]})
                                 
    stream = ffmpeg.output(v, main.audio, output_path).overwrite_output()
    run_command(stream, description="Watermarking", show_progress=True)

def _do_reverse(state, params):
    output_path = get_output_path(state.input_file, "reversed")
    if not confirm_overwrite(state, output_path): return
    state.add_log("Reversing video (this is slow)...")
    
    input_stream = ffmpeg.input(state.input_file)
    v = input_stream.video.filter('reverse')
    a = input_stream.audio.filter('areverse')
    stream = ffmpeg.output(v, a, output_path).overwrite_output()
    
    run_command(stream, description="Reversing...", show_progress=True)

def _do_rotate(state, params):
    mode = params.get('rotation', '90 Clockwise')
    output_path = get_output_path(state.input_file, "rotated")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Rotating: {mode}")
    input_stream = ffmpeg.input(state.input_file)
    
    if "Counter" in mode: transpose = 2
    elif "180" in mode: transpose = None
    else: transpose = 1 # 90 Clockwise
    
    if transpose:
        v = input_stream.video.filter('transpose', transpose)
    else:
        v = input_stream.video.filter('hflip').filter('vflip')
        
    stream = ffmpeg.output(v, input_stream.audio, output_path).overwrite_output()
    run_command(stream, description="Rotating...", show_progress=True)

def _do_flip(state, params):
    direction = params.get('direction', 'Horizontal')
    output_path = get_output_path(state.input_file, f"flipped_{direction[0].lower()}")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Flipping {direction}...")
    
    input_stream = ffmpeg.input(state.input_file)
    filter_name = 'hflip' if direction == "Horizontal" else 'vflip'
    
    v = input_stream.video.filter(filter_name)
    stream = ffmpeg.output(v, input_stream.audio, output_path).overwrite_output()
    run_command(stream, description="Flipping...", show_progress=True)

def _do_crop(state, params):
    x = params.get('x', 0)
    y = params.get('y', 0)
    w = params.get('w', 100)
    h = params.get('h', 100)
    
    output_path = get_output_path(state.input_file, "cropped")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Cropping: x={x} y={y} w={w} h={h}")
    
    stream = ffmpeg.input(state.input_file).crop(x, y, w, h).output(output_path).overwrite_output()
    run_command(stream, description="Cropping...", show_progress=True)

def _do_resize(state, params):
    w = params.get('width', -1)
    h = params.get('height', -1)
    output_path = get_output_path(state.input_file, "resized")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Resizing to {w}x{h}")
    
    stream = ffmpeg.input(state.input_file).filter('scale', w, h).output(output_path).overwrite_output()
    run_command(stream, description="Resizing...", show_progress=True)

def _do_img_convert(state, params):
    fmt = params.get('format', 'png')
    output_path = get_output_path(state.input_file, "converted", f".{fmt}")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Converting image to {fmt}...")
    stream = ffmpeg.input(state.input_file).output(output_path).overwrite_output()
    run_command(stream, description="Image Convert", show_progress=True)

def _do_img_rotate(state, params):
    mode = params.get('rotation', '90 Clockwise')
    output_path = get_output_path(state.input_file, "rotated")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Rotating Image: {mode}")
    if "Counter" in mode: transpose = 2
    elif "180" in mode: transpose = None
    else: transpose = 1
    
    v = ffmpeg.input(state.input_file)
    if transpose: v = v.filter('transpose', transpose)
    else: v = v.filter('hflip').filter('vflip')
    
    stream = v.output(output_path).overwrite_output()
    run_command(stream, description="Image Rotate", show_progress=True)

def _do_img_flip(state, params):
    direction = params.get('direction', 'Horizontal')
    output_path = get_output_path(state.input_file, f"flipped_{direction[0].lower()}")
    if not confirm_overwrite(state, output_path): return
    state.add_log(f"Flipping Image {direction}...")
    
    filter_name = 'hflip' if direction == "Horizontal" else 'vflip'
    stream = ffmpeg.input(state.input_file).filter(filter_name).output(output_path).overwrite_output()
    run_command(stream, description="Image Flip", show_progress=True)

def _do_stabilize(state, params):
    shakiness = params.get('shakiness', 5)
    smoothing = params.get('smoothing', 10)
    output_path = get_output_path(state.input_file, "stabilized")
    transforms_path = os.path.join(tempfile.gettempdir(), "transforms.trf")
    
    state.add_log("Stabilizing (Pass 1/2: Analyze)...")
    try:
        # Pass 1
        (
            ffmpeg.input(state.input_file)
            .filter('vidstabdetect', shakiness=shakiness, result=transforms_path)
            .output(os.devnull, f='null')
            .overwrite_output()
            .run(quiet=True)
        )
        
        # Pass 2
        state.add_log("Stabilizing (Pass 2/2: Transform)...")
        stream = (
            ffmpeg.input(state.input_file)
            .filter('vidstabtransform', input=transforms_path, smoothing=smoothing)
            .output(output_path)
        )
        run_command(stream, description="Stabilizing...", show_progress=True)
        
    except ffmpeg.Error as e:
        state.add_log(f"FFmpeg Error: {e.stderr.decode() if e.stderr else str(e)}")
    finally:
        if os.path.exists(transforms_path): os.remove(transforms_path)

def _do_extract_audio(state, params):
    fmt = params.get('fmt', 'mp3')
    output_path = get_output_path(state.input_file, "audio", f".{fmt}")
    state.add_log(f"Extracting audio to {fmt}...")
    
    kwargs = {'vn': None}
    if fmt == 'mp3':
        kwargs['acodec'] = 'libmp3lame'
        kwargs['audio_bitrate'] = '192k'
        
    stream = ffmpeg.input(state.input_file).output(output_path, **kwargs)
    run_command(stream, description="Extracting Audio...", show_progress=True)

def _do_remove_audio(state, params):
    output_path = get_output_path(state.input_file, "silent")
    state.add_log("Removing audio track...")
    
    stream = ffmpeg.input(state.input_file).output(output_path, vcodec='copy', an=None)
    run_command(stream, description="Removing Audio...", show_progress=True)

def _do_volume(state, params):
    vol = params.get('vol', 1.0)
    output_path = get_output_path(state.input_file, "volume")
    state.add_log(f"Adjusting volume by {vol}x...")
    
    input_stream = ffmpeg.input(state.input_file)
    a = input_stream.audio.filter('volume', volume=vol)
    stream = ffmpeg.output(input_stream.video, a, output_path, vcodec='copy')
    run_command(stream, description="Adjusting Volume...", show_progress=True)

def _do_fade_audio(state, params):
    in_sec = params.get('in', 0.0)
    out_sec = params.get('out', 0.0)
    duration = get_video_duration(state.input_file)
    output_path = get_output_path(state.input_file, "afade")
    
    state.add_log(f"Audio Fade: In={in_sec}s, Out={out_sec}s")
    
    input_stream = ffmpeg.input(state.input_file)
    a = input_stream.audio
    
    if in_sec > 0:
        a = a.filter('afade', t='in', st=0, d=in_sec)
    if out_sec > 0:
        start = duration - out_sec
        a = a.filter('afade', t='out', st=start, d=out_sec)
        
    stream = ffmpeg.output(input_stream.video, a, output_path, vcodec='copy')
    run_command(stream, description="Fading Audio...", show_progress=True)

def _do_normalize_audio(state, params):
    method = params.get('method', 'EBU R128')
    output_path = get_output_path(state.input_file, "normalized")
    state.add_log(f"Normalizing ({method})...")
    
    input_stream = ffmpeg.input(state.input_file)
    a = input_stream.audio
    
    if method == "EBU R128":
        a = a.filter('loudnorm', I=-14, TP=-1.5, LRA=11)
    elif method == "Peak":
        a = a.filter('loudnorm', I=-24, TP=-1.0, linear=True)
    elif method == "Dynamic":
        a = a.filter('dynaudnorm')
        
    stream = ffmpeg.output(input_stream.video, a, output_path, vcodec='copy')
    run_command(stream, description="Normalizing...", show_progress=True)

def _do_color_correction(state, params):
    b = params.get('brightness', 0.0)
    c = params.get('contrast', 1.0)
    s = params.get('saturation', 1.0)
    output_path = get_output_path(state.input_file, "corrected")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Applying Color Correction: B={b}, C={c}, S={s}")
    stream = (
        ffmpeg.input(state.input_file)
        .filter('eq', brightness=b, contrast=c, saturation=s)
        .output(output_path, acodec='copy')
        .overwrite_output()
    )
    run_command(stream, description="Color Correction", show_progress=True)

def _do_denoise(state, params):
    luma = params.get('luma', 4.0)
    chroma = params.get('chroma', 3.0)
    output_path = get_output_path(state.input_file, "denoised")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Denoising: Luma={luma}, Chroma={chroma}")
    stream = (
        ffmpeg.input(state.input_file)
        .filter('hqdn3d', luma_spatial=luma, chroma_spatial=chroma)
        .output(output_path, acodec='copy')
        .overwrite_output()
    )
    run_command(stream, description="Denoising", show_progress=True)

def _do_fade_video(state, params):
    in_sec = params.get('in', 0.0)
    out_sec = params.get('out', 0.0)
    duration = get_video_duration(state.input_file)
    output_path = get_output_path(state.input_file, "vfade")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Video Fade: In={in_sec}s, Out={out_sec}s")
    v = ffmpeg.input(state.input_file).video
    if in_sec > 0:
        v = v.filter('fade', t='in', st=0, d=in_sec)
    if out_sec > 0:
        v = v.filter('fade', t='out', st=duration - out_sec, d=out_sec)
        
    stream = ffmpeg.output(v, ffmpeg.input(state.input_file).audio, output_path).overwrite_output()
    run_command(stream, description="Video Fade", show_progress=True)

def _do_loop(state, params):
    count = params.get('count', 2)
    output_path = get_output_path(state.input_file, "looped")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Looping video {count} times...")
    # Using input argument for stream_loop
    stream = ffmpeg.input(state.input_file, stream_loop=count).output(output_path, c='copy').overwrite_output()
    run_command(stream, description="Looping", show_progress=True)

def _do_extract_frames(state, params):
    interval = params.get('interval', 1.0)
    fmt = params.get('fmt', 'png')
    
    p = Path(state.input_file)
    out_dir = state.output_dir if state.output_dir else str(p.parent)
    out_pattern = os.path.join(out_dir, f"{p.stem}_frame_%03d.{fmt}")
    
    state.add_log(f"Extracting frames every {interval}s to {fmt}...")
    stream = (
        ffmpeg.input(state.input_file)
        .filter('fps', fps=1.0/interval)
        .output(out_pattern)
        .overwrite_output()
    )
    run_command(stream, description="Extracting Frames", show_progress=True)

def _do_split(state, params):
    method = params.get('method', 'Equal Parts')
    val = params.get('val', 2)
    duration = get_video_duration(state.input_file)
    
    state.add_log(f"Splitting: {method} = {val}")
    
    segment_time = 0
    if method == "Equal Parts":
        segment_time = duration / val
    else:
        segment_time = val
        
    output_pattern = get_output_path(state.input_file, "part%03d")
    
    # f=segment
    stream = ffmpeg.input(state.input_file).output(
        output_pattern, 
        c='copy', 
        f='segment', 
        segment_time=segment_time, 
        reset_timestamps=1
    )
    run_command(stream, description="Splitting...", show_progress=True)

def _do_inspect(state, params):
    state.add_log("Inspecting File...")
    try:
        info = ffmpeg.probe(state.input_file)
        # Pretty print JSON to log
        formatted = json.dumps(info, indent=2)
        state.add_log(formatted)
    except Exception as e:
        state.add_log(f"Error probing file: {e}")

def _do_metadata(state, params):
    output_path = get_output_path(state.input_file, "meta")
    if not confirm_overwrite(state, output_path): return
    
    kwargs = {'c': 'copy'}
    # FFmpeg-python allows multiple metadata entries by using metadata as a list
    # or by passing them as individual arguments if the wrapper supports it.
    # The most reliable way with run_command (which uses ffmpeg.run) is often:
    meta_args = []
    if params.get('title'): meta_args.append(f"title={params['title']}")
    if params.get('artist'): meta_args.append(f"artist={params['artist']}")
    if params.get('album'): meta_args.append(f"album={params['album']}")
    if params.get('year'): meta_args.append(f"date={params['year']}")
    if params.get('comment'): meta_args.append(f"comment={params['comment']}")
    
    state.add_log(f"Updating metadata: {meta_args}")
    
    # We'll use a manual command construction for metadata to be 100% sure
    # because ffmpeg-python's metadata handling can be finicky with multiple tags
    cmd = ['ffmpeg', '-y', '-i', state.input_file]
    for arg in meta_args:
        cmd.extend(['-metadata', arg])
    cmd.extend(['-c', 'copy', output_path])
    
    import subprocess
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    if proc.returncode == 0:
        state.add_log("Metadata updated successfully!")
    else:
        state.add_log(f"Metadata update failed: {err}")

def _do_music_separation(state, params):
    try:
        import demucs.separate
    except ImportError:
        state.add_log("Error: 'demucs' not installed. pip install demucs")
        return

    stems = params.get('stems', '2')[0] # Get first char '2', '4', '6'
    fmt = params.get('fmt', 'mp3')
    
    out_dir = state.output_dir if state.output_dir else os.path.dirname(state.input_file)
    cmd = [sys.executable, "-m", "demucs.separate", "-o", out_dir, "-n", "htdemucs", state.input_file]
    
    if stems == '2': cmd.extend(["--two-stems", "vocals"])
    elif stems == '6': cmd.extend(["-n", "htdemucs_6s"])
    
    if fmt == 'mp3': cmd.extend(["--mp3", "--mp3-bitrate", "320"])
    elif fmt == 'flac': cmd.append("--flac")
    
    state.add_log(f"Running Demucs ({stems} stems)...")
    import subprocess
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Stream output
    for line in proc.stdout:
        state.add_log(line.strip())
    proc.wait()
    
    if proc.returncode == 0:
        state.add_log("Separation complete.")
    else:
        state.add_log("Demucs failed.")

def _do_remove_background(state, params):
    try:
        from rembg import remove
        from PIL import Image
    except ImportError:
        state.add_log("Error: 'rembg' not installed.")
        return

    bg_type = params.get('type', 'Transparent')
    
    # Check if it's an image or video
    ext = Path(state.input_file).suffix.lower()
    is_video = ext in ['.mp4', '.mkv', '.mov', '.webm', '.avi']

    if not is_video:
        output_path = get_output_path(state.input_file, "nobg", ".png")
        state.add_log("Removing background (Image)...")
        try:
            img = Image.open(state.input_file)
            out = remove(img)
            if "Black" in bg_type:
                bg = Image.new("RGBA", out.size, (0,0,0,255))
                bg.paste(out, mask=out); out = bg.convert("RGB")
            elif "White" in bg_type:
                bg = Image.new("RGBA", out.size, (255,255,255,255))
                bg.paste(out, mask=out); out = bg.convert("RGB")
            out.save(output_path)
            state.add_log(f"Saved to {output_path}")
        except Exception as e: state.add_log(f"Error: {e}")
    else:
        # Video Background Removal (Frame by frame)
        output_path = get_output_path(state.input_file, "nobg", ".webm" if "Transparent" in bg_type else ".mp4")
        if not confirm_overwrite(state, output_path): return
        state.add_log("Removing background (Video) - This will be SLOW...")
        
        # Use subprocess to call rembg's CLI if available, or do it here
        # Doing it here for better integration with state
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(state.input_file)
        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        temp_out = os.path.join(tempfile.gettempdir(), "rembg_temp.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(temp_out, fourcc, fps, (w, h))
        
        count = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            # Convert to PIL
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            nobg = remove(img)
            
            # Handle background color
            if "Black" in bg_type:
                bg = Image.new("RGBA", nobg.size, (0,0,0,255))
                bg.paste(nobg, mask=nobg); final_img = bg.convert("RGB")
            elif "White" in bg_type:
                bg = Image.new("RGBA", nobg.size, (255,255,255,255))
                bg.paste(nobg, mask=nobg); final_img = bg.convert("RGB")
            elif "Green" in bg_type:
                bg = Image.new("RGBA", nobg.size, (0,255,0,255))
                bg.paste(nobg, mask=nobg); final_img = bg.convert("RGB")
            else: # Transparent - but MP4 doesn't support transparency easily here
                final_img = nobg.convert("RGB")
                
            out_writer.write(cv2.cvtColor(np.array(final_img), cv2.COLOR_RGB2BGR))
            count += 1
            if count % 10 == 0: state.add_log(f"Processed {count}/{total} frames...")
            
        cap.release()
        out_writer.release()
        
        # Merge with original audio
        state.add_log("Merging audio...")
        import subprocess
        # Using subprocess for reliable mapping of optional audio
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', temp_out,
            '-i', state.input_file,
            '-map', '0:v:0',
            '-map', '1:a?',
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-shortest',
            output_path
        ]
        
        proc = subprocess.run(merge_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            state.add_log(f"Merge failed: {proc.stderr}")
        
        if os.path.exists(temp_out): os.remove(temp_out)
        state.add_log("Background removal complete.")

def _do_blur_faces(state, params):
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
    except ImportError:
        state.add_log("Error: opencv-python or mediapipe not installed.")
        return

    method = params.get('method', 'MediaPipe AI (Accurate)')
    sense = params.get('sensitivity', 'Medium')
    strength = params.get('strength', 'Medium')
    pad_pct = params.get('padding', 0.2)
    
    min_conf = 0.4
    if sense == "High": min_conf = 0.2
    elif sense == "Low": min_conf = 0.6
    
    output_path = get_output_path(state.input_file, "faces_blurred")
    if not confirm_overwrite(state, output_path): return
    
    state.add_log(f"Initializing Face Detector ({method})...")
    
    cap = cv2.VideoCapture(state.input_file)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    temp_out = os.path.join(tempfile.gettempdir(), "blur_temp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(temp_out, fourcc, fps, (w, h))

    # Initialize Detector
    face_cascade = None
    if "OpenCV" in method:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        # Map confidence
        sf, mn = 1.2, 5
        if sense == "High": sf, mn = 1.1, 3
        elif sense == "Low": sf, mn = 1.3, 7
    else:
        mp_face_detection = mp.solutions.face_detection
        detector = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=min_conf)

    try:
        count = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            face_boxes = []
            if face_cascade:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=sf, minNeighbors=mn, minSize=(30, 30))
                for (fx, fy, fw, fh) in faces:
                    face_boxes.append((fx, fy, fw, fh))
            else:
                results = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if results.detections:
                    for detection in results.detections:
                        bbox = detection.location_data.relative_bounding_box
                        face_boxes.append((int(bbox.xmin * w), int(bbox.ymin * h), int(bbox.width * w), int(bbox.height * h)))
            
            for (x, y, bw, bh) in face_boxes:
                # Apply Padding
                px = int(bw * pad_pct)
                py = int(bh * pad_pct)
                x, y = max(0, x-px), max(0, y-py)
                bw, bh = min(w-x, bw+2*px), min(h-y, bh+2*py)
                
                face = frame[y:y+bh, x:x+bw]
                if face.size > 0:
                    if "Light" in strength: f_blur = cv2.GaussianBlur(face, (31, 31), 10)
                    elif "Heavy" in strength: f_blur = cv2.GaussianBlur(face, (151, 151), 50)
                    elif "Pixelate" in strength:
                        small = cv2.resize(face, (max(1, bw//16), max(1, bh//16)), interpolation=cv2.INTER_LINEAR)
                        f_blur = cv2.resize(small, (bw, bh), interpolation=cv2.INTER_NEAREST)
                    else: # Medium
                        f_blur = cv2.GaussianBlur(face, (71, 71), 25)
                    frame[y:y+bh, x:x+bw] = f_blur
            
            out_writer.write(frame)
            count += 1
            if count % 20 == 0: state.add_log(f"Blurred faces in {count}/{total} frames...")
    finally:
        cap.release()
        out_writer.release()
        if not face_cascade: detector.close()
        
        state.add_log("Merging audio...")
        import subprocess
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', temp_out,
            '-i', state.input_file,
            '-map', '0:v:0',
            '-map', '1:a?',
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-shortest',
            output_path
        ]
        
        proc = subprocess.run(merge_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            state.add_log(f"Merge failed: {proc.stderr}")
    
        if os.path.exists(temp_out): os.remove(temp_out)
        state.add_log("Face blurring complete.")

def _do_subtitles(state, params):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        state.add_log("Error: 'faster-whisper' not installed. pip install faster-whisper")
        return

    model_size = params.get('model', 'base')
    mode = params.get('mode', 'Sidecar (.srt)')
    lang = params.get('lang', 'auto')
    if lang == 'auto': lang = None

    state.add_log(f"Loading Whisper Model ({model_size})...")
    # Extract Audio
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    state.add_log("Extracting audio for transcription...")
    
    import subprocess
    extract_cmd = [
        'ffmpeg', '-y',
        '-i', state.input_file,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        audio_path
    ]
    
    proc = subprocess.run(extract_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        state.add_log(f"Audio extraction failed: {proc.stderr}")
        return

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        state.add_log("Transcribing...")
        
        segments, info = model.transcribe(audio_path, language=lang)
        
        # Collect segments
        subs = []
        total_duration = info.duration
        state.add_log(f"Detected audio duration: {total_duration:.2f}s")
        
        for segment in segments:
            # Simple SRT formatting
            start = time.strftime('%H:%M:%S,000', time.gmtime(segment.start))
            end = time.strftime('%H:%M:%S,000', time.gmtime(segment.end))
            text = segment.text.strip()
            subs.append(f"{segment.id}\n{start} --> {end}\n{text}\n")
            
            # Update Progress based on transcription position
            progress = segment.end / total_duration if total_duration > 0 else 0
            state.set_progress(progress)
            if segment.id % 5 == 0:
                state.add_log(f"Transcribed {segment.end:.1f}s / {total_duration:.1f}s...")
        
        state.set_progress(1.0)
        srt_content = "\n".join(subs)
        
        if "Sidecar" in mode:
            srt_path = get_output_path(state.input_file, "", ".srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            state.add_log(f"Saved SRT: {srt_path}")
            
        elif "Burn-in" in mode:
            # Save temp srt
            temp_srt = os.path.join(tempfile.gettempdir(), "temp.srt")
            try:
                with open(temp_srt, "w", encoding="utf-8") as f:
                    f.write(srt_content)

                output_path = get_output_path(state.input_file, "subtitled")
                state.add_log("Burning subtitles (re-encoding)...")
                
                # Robust escaping for FFmpeg filters
                # 1. Single quotes around the path
                # 2. Escape colons with backslash
                # 3. Escape single quotes in path
                safe_srt_path = temp_srt.replace("'", "'\\\\''").replace(":", "\\:")
                
                # We use a direct subprocess for the burn-in to have better control
                state.add_log("Starting FFmpeg burn-in process...")
                cmd = [
                    'ffmpeg', '-y',
                    '-i', state.input_file,
                    '-vf', f"subtitles='{safe_srt_path}'",
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k',
                    output_path
                ]
                
                # We'll use subprocess.Popen to monitor progress in the GUI
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                duration = get_video_duration(state.input_file)
                
                for line in proc.stderr:
                    if "time=" in line and duration > 0:
                        try:
                            time_str = line.split("time=")[1].split(" ")[0].strip()
                            h, m, s = map(float, time_str.split(':'))
                            elapsed = h * 3600 + m * 60 + s
                            state.set_progress(elapsed / duration)
                        except: pass
                
                proc.wait()
                if proc.returncode == 0:
                    state.add_log("Burn-in successful.")
                    state.set_progress(1.0)
                else:
                    state.add_log(f"Burn-in failed: {proc.stderr.read()}")
            finally:
                if os.path.exists(temp_srt): os.remove(temp_srt)

    finally:
        if os.path.exists(audio_path): os.remove(audio_path)

def _do_auto_dub(state, params):
    from peg_this.features.dubbing import run_dubbing_pipeline, LANGUAGES
    
    target_lang_name = params.get('lang', 'Spanish')
    model_size = params.get('model', 'base')
    
    if target_lang_name not in LANGUAGES:
        state.add_log(f"Error: Language {target_lang_name} not supported.")
        return
        
    output_path = get_output_path(state.input_file, f"dubbed_{target_lang_name.lower()}")
    if not confirm_overwrite(state, output_path): return

    def progress_wrapper(p):
        state.set_progress(p)

    def log_wrapper(msg):
        state.add_log(msg)

    state.add_log(f"Starting Auto-Dubbing ({target_lang_name})...")
    success = run_dubbing_pipeline(
        input_file=state.input_file,
        output_path=output_path,
        target_lang_name=target_lang_name,
        model_size=model_size,
        progress_callback=progress_wrapper,
        log_callback=log_wrapper
    )

    if success:
        state.add_log(f"Dubbing complete: {output_path}")
        state.last_generated_file = output_path # Ensure chaining works
    else:
        state.add_log("Dubbing failed.")

def _do_brainrot(state, params):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        state.add_log("Error: faster-whisper not installed.")
        return

    style = params.get('style', 'Classic')
    model_size = params.get('model', 'base')
    output_path = get_output_path(state.input_file, "brainrot")
    
    # 1. Extract Audio
    audio_path = os.path.join(tempfile.gettempdir(), "temp_audio.wav")
    state.add_log("Extracting audio for transcription...")
    
    import subprocess
    extract_cmd = [
        'ffmpeg', '-y',
        '-i', state.input_file,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        audio_path
    ]
    
    proc = subprocess.run(extract_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        state.add_log(f"Audio extraction failed: {proc.stderr}")
        return

    try:
        # 2. Transcribe with Word Timestamps
        state.add_log(f"Transcribing ({model_size})...")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, word_timestamps=True)
        
        total_duration = info.duration
        all_words = []
        for segment in segments:
            if segment.words:
                for word in segment.words:
                    all_words.append({'text': word.word.strip(), 'start': word.start, 'end': word.end})
            
            # Update Progress
            progress = segment.end / total_duration if total_duration > 0 else 0
            state.set_progress(progress)
            if segment.id % 5 == 0:
                state.add_log(f"Transcribed {segment.end:.1f}s / {total_duration:.1f}s...")
        
        state.set_progress(1.0)
        state.add_log(f"Found {len(all_words)} words.")
        
        # 3. Generate ASS
        ass_path = os.path.join(tempfile.gettempdir(), "captions.ass")
        
        # Logic adapted from features/subtitle.py
        # Simplification: Use fixed resolution or probe input
        # We'll probe input to get dimensions
        probe = ffmpeg.probe(state.input_file, select_streams='v')
        width = int(probe['streams'][0]['width'])
        height = int(probe['streams'][0]['height'])
        font_size = int(height / 12)
        margin_v = int(height * 0.4) # Center
        
        # Styles
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        
        if "Highlighted" in style: highlight_color = "&H0000FFFF" # Yellow
        else: highlight_color = None
        
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,Arial Black,{font_size},{primary_color},{outline_color},&H00000000,-1,1,4,2,2,10,10,{margin_v}
[Events]
Format: Layer, Start, End, Style, Text
"""
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header)
            
            # Group words into phrases of 4
            chunk_size = 4
            for i in range(0, len(all_words), chunk_size):
                chunk = all_words[i:i+chunk_size]
                if not chunk: continue
                
                phrase_start = chunk[0]['start']
                phrase_end = chunk[-1]['end']
                
                # Create events for each word in this chunk to highlight it
                for j, word in enumerate(chunk):
                    w_start = word['start']
                    w_end = word['end']
                    
                    # Build text: highlight current word
                    text_parts = []
                    for k, w in enumerate(chunk):
                        if k == j and highlight_color:
                            text_parts.append(f"{{\\c{highlight_color}}}{w['text']}{{\\c{primary_color}}}")
                        else:
                            text_parts.append(w['text'])
                    
                    full_text = " ".join(text_parts)
                    
                    def fmt_time(s):
                        h = int(s // 3600)
                        m = int((s % 3600) // 60)
                        sc = int(s % 60)
                        cs = int((s % 1) * 100)
                        return f"{h}:{m:02d}:{sc:02d}.{cs:02d}"

                    start_t = fmt_time(w_start)
                    end_t = fmt_time(w_end)
                    
                    f.write(f"Dialogue: 0,{start_t},{end_t},Default,{full_text}\n")

        # 4. Burn
        state.add_log("Burning captions...")
        safe_ass_path = ass_path.replace("'", "'\\\\''").replace(":", "\\:")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', state.input_file,
            '-vf', f"ass='{safe_ass_path}'",
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            output_path
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        for line in proc.stderr:
            if "time=" in line and total_duration > 0:
                try:
                    time_str = line.split("time=")[1].split(" ")[0].strip()
                    h, m, s = map(float, time_str.split(':'))
                    elapsed = h * 3600 + m * 60 + s
                    state.set_progress(elapsed / total_duration)
                except: pass
        
        proc.wait()
        if proc.returncode == 0:
            state.add_log("Brainrot captions complete.")
            state.set_progress(1.0)
        else:
            state.add_log(f"Brainrot failed: {proc.stderr.read()}")

    finally:
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(ass_path): os.remove(ass_path)

def _do_visualizer(state, params):
    style = params.get('style', 'Spectrum Bars')
    res_str = params.get('res', '1920x1080')
    w, h = map(int, res_str.split('x'))
    output_path = get_output_path(state.input_file, "viz", ".mp4")
    
    state.add_log(f"Generating Visualizer ({style})...")
    
    filter_complex = ""
    if "Spectrum" in style:
        filter_complex = f"[0:a]showspectrum=s={w}x{h}:mode=combined:color=magma:slide=scroll[v]"
    elif "Waveform" in style:
        filter_complex = f"[0:a]showwaves=s={w}x{h}:mode=cline:rate=30:colors=cyan[v]"
    elif "CQT" in style:
        filter_complex = f"[0:a]showcqt=s={w}x{h}[v]"
    else:
        filter_complex = f"[0:a]avectorscope=s={w}x{h}[v]"
        
    cmd = ['ffmpeg', '-y', '-i', state.input_file, '-filter_complex', filter_complex, '-map', '[v]', '-map', '0:a', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', output_path]
    
    import subprocess
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    state.add_log("Running ffmpeg...")
    # Monitor? run_command is better but filter_complex with mapped streams is tricky in ffmpeg-python without nice syntax.
    # We'll trust subprocess here or wrap it.
    out, err = proc.communicate()
    if proc.returncode == 0:
        state.add_log("Visualizer created!")
    else:
        state.add_log(f"Failed: {err}")

def _do_slideshow(state, params):
    # Input is a folder path in state.input_file? Or we use dirname of input file.
    if os.path.isdir(state.input_file):
        folder = state.input_file
    else:
        folder = os.path.dirname(state.input_file)
        
    state.add_log(f"Looking for images in {folder}...")
    images = [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith(('.jpg', '.png'))]
    
    if not images:
        state.add_log("No images found.")
        return
        
    output_path = os.path.join(folder, "slideshow.mp4")
    concat_file = os.path.join(tempfile.gettempdir(), "slides.txt")

    try:
        with open(concat_file, 'w') as f:
            for img in images:
                esc = img.replace("'", "'\\''")
                f.write(f"file '{esc}'\n")
                f.write(f"duration 3\n")
            f.write(f"file '{images[-1].replace("'", "'\\''")}'\n")

        state.add_log(f"Creating slideshow from {len(images)} images...")
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', output_path]

        import subprocess
        subprocess.run(cmd)
        state.add_log(f"Done: {output_path}")
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

# --- Dispatcher ---

def run_operation_threaded(operation_name_arg, params_arg):
    state = UIState()
    operation = state.selected_operation
    
    if not operation:
        state.add_log("No operation selected.")
        return
    if state.job_status == "Running":
        state.add_log("Job busy.")
        return
    if not state.input_file:
        state.add_log("Error: No input file.")
        return

    params = collect_parameters(operation)
    state.reset_job_state()
    state.update_status("Running")
    
    def worker():
        # Setup logging redirection
        log_handler = UILogHandler(state)
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        log_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)
        
        try:
            state.add_log(f"Starting: {operation}")
            
            if operation == "Trim": _do_trim(state, params)
            elif operation == "Convert Format": _do_convert(state, params)
            elif operation == "Compress": _do_compress(state, params)
            elif operation == "GIF": _do_gif(state, params)
            elif operation == "Speed": _do_speed(state, params)
            elif operation == "Slow motion": _do_optical_flow(state, params)
            elif operation == "PiP": _do_pip(state, params)
            elif operation == "Watermark": _do_watermark(state, params)
            elif operation == "Reverse": _do_reverse(state, params)
            elif operation == "Rotate": _do_rotate(state, params)
            elif operation == "Flip": _do_flip(state, params)
            elif operation == "Crop": _do_crop(state, params)
            elif operation == "Resize": _do_resize(state, params)
            elif operation == "Stabilize": _do_stabilize(state, params)
            elif operation == "Extract Audio": _do_extract_audio(state, params)
            elif operation == "Remove Audio": _do_remove_audio(state, params)
            elif operation == "Volume": _do_volume(state, params)
            elif operation == "Fade Audio": _do_fade_audio(state, params)
            elif operation == "Normalize Audio": _do_normalize_audio(state, params)
            elif operation == "Split": _do_split(state, params)
            elif operation == "Color Correction": _do_color_correction(state, params)
            elif operation == "Denoise": _do_denoise(state, params)
            elif operation == "Fade Video": _do_fade_video(state, params)
            elif operation == "Loop": _do_loop(state, params)
            elif operation == "Extract Frames": _do_extract_frames(state, params)
            elif operation == "Convert Format (Img)": _do_img_convert(state, params)
            elif operation == "Rotate (Img)": _do_img_rotate(state, params)
            elif operation == "Flip (Img)": _do_img_flip(state, params)
            elif operation == "Subtitles (Whisper)": _do_subtitles(state, params)
            elif operation == "AI Auto-Dubbing": _do_auto_dub(state, params)
            elif operation == "Music Separation": _do_music_separation(state, params)
            elif operation == "Remove Background": _do_remove_background(state, params)
            elif operation == "Blur Faces": _do_blur_faces(state, params)
            elif operation == "Inspect File": _do_inspect(state, params)
            elif operation == "Metadata": _do_metadata(state, params)
            elif operation == "Brainrot Captions": _do_brainrot(state, params)
            elif operation == "Audio Visualizer": _do_visualizer(state, params)
            elif operation == "Slideshow": _do_slideshow(state, params)
            else:
                state.add_log(f"Operation '{operation}' not implemented yet.")
                time.sleep(1)
            
            state.update_status("Completed")
            
            # Auto-load result into preview
            if state.last_generated_file and os.path.exists(state.last_generated_file):
                # Update input file for chaining operations
                state.input_file = state.last_generated_file
                # Queue this on main thread via state callback mechanism
                state.queue_callback(lambda: player.load_file(state.last_generated_file))
                
        except Exception as e:
            state.update_status("Failed")
            state.add_log(f"Error: {e}")
            import traceback
            state.add_log(traceback.format_exc())
        finally:
            root_logger.removeHandler(log_handler)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

def cancel_current_job():
    state = UIState()
    if state.job_status == "Running":
        state.add_log("Cancelling...")
        state.cancel_flag.set()