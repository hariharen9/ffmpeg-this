import time
import threading
import cv2
import numpy as np
import dearpygui.dearpygui as dpg
import os
import re

from peg_this.ui.state import UIState

class VideoPlayer:
    def __init__(self):
        self.cap = None
        self.file_path = None
        
        # State
        self.is_playing = False
        self.fps = 30.0
        self.total_frames = 0
        self.current_frame_idx = 0
        self.duration = 0.0
        self.width = 600
        self.height = 400
        
        # Playback control
        self.last_update_time = time.time()
        self.speed = 1.0
        self.seek_requested = -1
        
        # Texture - Tag must match layout.py
        self.texture_tag = "video_texture"
        self.texture_width = 600
        self.texture_height = 400
        
        # Subtitles
        self.subtitles = [] 
        self.show_subtitles = True
        self.subtitle_offset = 0.0

    # Note: Texture creation is now handled in layout.py to ensure correct context

    def init_dpg(self):
        # Legacy: No longer needed, kept for compatibility if called
        pass

    def load_file(self, file_path):
        if self.cap:
            self.cap.release()
        
        if not os.path.exists(file_path):
            return

        self.file_path = file_path
        self.cap = cv2.VideoCapture(file_path)
        
        if not self.cap.isOpened():
            print(f"Failed to open {file_path}")
            return

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps else 0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.current_frame_idx = 0
        self.is_playing = False
        
        # Try to load sidecar subtitles
        srt_path = os.path.splitext(file_path)[0] + ".srt"
        if os.path.exists(srt_path):
            self.load_subtitles(srt_path)
        else:
            self.subtitles = []

        # Read first frame
        self.update_frame()
        self._update_ui_state()

    def load_subtitles(self, srt_path):
        self.subtitles = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:(?!\n\n).)*)', re.DOTALL)
            matches = pattern.findall(content)
            
            for m in matches:
                start_str = m[1].replace(',', '.')
                end_str = m[2].replace(',', '.')
                text = m[3].strip()
                def to_sec(t_str):
                    h, m, s = t_str.split(':')
                    return int(h) * 3600 + int(m) * 60 + float(s)
                self.subtitles.append((to_sec(start_str), to_sec(end_str), text))
            print(f"Loaded {len(self.subtitles)} subtitles.")
        except Exception:
            pass

    def unload(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.file_path = None
        self.is_playing = False
        self.current_frame_idx = 0
        
        # Reset to Noise/Black
        blank = np.zeros((400, 600, 4), dtype=np.float32)
        blank[:, :, 3] = 1.0 # Opaque
        dpg.set_value(self.texture_tag, blank.flatten().tolist())
        self._update_ui_state()

    def play(self):
        self.is_playing = True
        self.last_update_time = time.time()

    def pause(self):
        self.is_playing = False

    def toggle_play(self):
        if self.is_playing: self.pause()
        else: self.play()

    def seek(self, frame_idx):
        if self.cap:
            frame_idx = max(0, min(frame_idx, self.total_frames - 1))
            self.seek_requested = frame_idx
            if not self.is_playing:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                self.current_frame_idx = frame_idx
                self.update_frame()

    def _get_current_subtitle_text(self, current_time):
        if not self.show_subtitles: return None
        for start, end, text in self.subtitles:
            if start <= current_time <= end:
                return text
        return None

    def update(self):
        if not self.cap or not self.cap.isOpened():
            return

        now = time.time()
        if self.is_playing:
            dt = now - self.last_update_time
            target_fps = self.fps * self.speed
            
            if dt >= (1.0 / target_fps):
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                    self._process_and_render(frame)
                    self.last_update_time = now
                    self._update_ui_state()
                else:
                    self.pause()

        if self.seek_requested >= 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.seek_requested)
            ret, frame = self.cap.read()
            if ret:
                self.current_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self._process_and_render(frame)
            self.seek_requested = -1

    def update_frame(self):
        if self.cap:
            ret, frame = self.cap.read()
            if ret:
                self._process_and_render(frame)

    def _process_and_render(self, frame):
        fh, fw = frame.shape[:2]
        th, tw = self.texture_height, self.texture_width
        
        scale = min(tw/fw, th/fh)
        nw, nh = int(fw * scale), int(fh * scale)
        
        resized = cv2.resize(frame, (nw, nh))
        
        # Subtitles
        current_time = self.current_frame_idx / self.fps
        sub_text = self._get_current_subtitle_text(current_time)
        if sub_text:
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.8
            thickness = 2
            text_size = cv2.getTextSize(sub_text, font, font_scale, thickness)[0]
            text_x = (nw - text_size[0]) // 2
            text_y = nh - 30
            cv2.putText(resized, sub_text, (text_x, text_y), font, font_scale, (0,0,0), thickness+3, cv2.LINE_AA)
            cv2.putText(resized, sub_text, (text_x, text_y), font, font_scale, (255,255,255), thickness, cv2.LINE_AA)

        # Canvas
        canvas = np.zeros((th, tw, 3), dtype=np.uint8)
        y_off = (th - nh) // 2
        x_off = (tw - nw) // 2
        canvas[y_off:y_off+nh, x_off:x_off+nw] = resized
        
        canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGBA)
        canvas[:, :, 3] = 255 # Force Opaque
        
        # Convert to list for safety on all platforms
        data = canvas.astype(np.float32) / 255.0
        dpg.set_value(self.texture_tag, data.flatten().tolist())

    def _update_ui_state(self):
        if dpg.does_item_exist("preview_seek_slider"):
            dpg.set_value("preview_seek_slider", self.current_frame_idx)
            dpg.configure_item("preview_seek_slider", max_value=max(1, self.total_frames-1))
        
        if dpg.does_item_exist("preview_time_text"):
            cur = self.current_frame_idx / self.fps if self.fps else 0
            tot = self.duration
            def fmt(s): return f"{int(s//60):02d}:{int(s%60):02d}"
            dpg.set_value("preview_time_text", f"{fmt(cur)} / {fmt(tot)}")

player = VideoPlayer()
