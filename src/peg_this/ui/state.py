"""
Shared UI state for the DearPyGui interface.
"""
import threading
from typing import Optional, Dict, List, Callable

class UIState:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(UIState, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        with self._lock:
            if self._initialized:
                return
            
            # Core state
            self.input_file: Optional[str] = None
            self.output_dir: Optional[str] = None
            self.selected_operation: Optional[str] = None
            self.operation_params: Dict = {}
            self.last_generated_file: Optional[str] = None

            # Job state
            self.job_status: str = "Idle"
            self.job_progress: float = 0.0
            self.job_logs: List[str] = []
            self.cancel_flag: threading.Event = threading.Event()
            
            # Threading
            self.dpg_queue: List[Callable] = []
            self.queue_lock: threading.Lock = threading.Lock()
            
            self._initialized = True

    def update_status(self, status: str):
        self.job_status = status
        self.queue_callback(lambda: None)  # Trigger UI refresh if needed

    def add_log(self, message: str):
        with self.queue_lock:
            self.job_logs.append(message)
            # Optional: Limit log size
            if len(self.job_logs) > 1000:
                self.job_logs.pop(0)

    def set_progress(self, value: float):
        self.job_progress = max(0.0, min(1.0, value))

    def queue_callback(self, callback: Callable):
        """Thread-safe method to queue UI updates from background threads."""
        with self.queue_lock:
            self.dpg_queue.append(callback)

    def process_queue(self):
        """Process queued callbacks. Must be called from the main thread."""
        with self.queue_lock:
            while self.dpg_queue:
                callback = self.dpg_queue.pop(0)
                try:
                    callback()
                except Exception as e:
                    print(f"Error in UI callback: {e}")

    def reset_job_state(self):
        self.job_status = "Idle"
        self.job_progress = 0.0
        self.cancel_flag.clear()