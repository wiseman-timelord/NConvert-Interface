# Script: launcher.py - NConvert-Interface
# Compatible with Python 3.10–3.12 and Windows 8.1–11
# Windows 10+: Gradio 5.49.1 + PyQt6 WebEngine
# Windows 8.1: Gradio 3.50.2 + PyQt5 WebEngine (Chromium 83 compatible)
# ─── Early Init: Read constants.ini & set Qt env BEFORE any Qt imports ─────────
import os
import sys
import configparser

# Read system constants written by the installer
_ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "constants.ini")
_config = configparser.ConfigParser()
_config.read(_ini_path, encoding="utf-8")

WINDOWS_VERSION = _config.get("system", "os_version", fallback="unknown")
PYTHON_VERSION = _config.get("system", "python_version", fallback="unknown")
WORKING_DIRECTORY = _config.get("system", "working_directory",
                                fallback=os.path.dirname(os.path.abspath(__file__)))

# ─── QtWebEngine GPU Workaround ────────────────────────────────────────────────
# Only disable GPU on older Windows where GPU/OpenGL support is limited.
# On Windows 10+ the GPU pipeline works; forcing software mode actually causes
# GLES3 context creation errors in the Chromium subprocess.
if WINDOWS_VERSION in ("win81", "win8", "win7"):
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    os.environ["QT_OPENGL"] = "software"

# ─── Remaining Imports ─────────────────────────────────────────────────────────
print("Starting Imports...")
import time
import gradio as gr
GRADIO_MAJOR = int(gr.__version__.split('.')[0])
from threading import Timer, Thread
import subprocess
import asyncio
import psutil
import socket
from pathlib import Path
import json
from tkinter import filedialog
import winsound
import platform
import ctypes
import signal
import atexit
print("..Imports Completed.")
print("Initializing Program...")
# ─── Global References ──────────────────────────────────────────────────────────
global_demo = None
_shutdown_requested = False
# ─── OS / Path info from constants.ini ──────────────────────────────────────────
print(f"Detected OS: {WINDOWS_VERSION}")
print(f"Python: {PYTHON_VERSION}")
print(f"Working Dir: {WORKING_DIRECTORY}")
# ─── Paths & Globals ────────────────────────────────────────────────────────────
workspace_path = os.path.join(WORKING_DIRECTORY, "temp")
DATA_DIR = Path(WORKING_DIRECTORY) / "data"
SETTINGS_FILE = DATA_DIR / "persistent.json"
nconvert_path = str(DATA_DIR / "NConvert" / "nconvert.exe")
allowed_formats = ["JPEG", "PNG", "BMP", "GIF", "TIFF", "AVIF", "WEBP", "ICO", "PSD", "PSPIMAGE"]

# Session defaults
_session = {
    "last_folder": workspace_path,
    "last_from": "PSPIMAGE",
    "last_to": "JPEG",
    "last_delete": False,
    "beep_on_complete": False
}

# Load last session if exists
if SETTINGS_FILE.exists():
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            candidate = Path(data.get("last_folder", "."))
            if candidate.exists() and candidate.is_dir():
                _session["last_folder"] = str(candidate.resolve())
            _session["last_from"] = data.get("last_from", _session["last_from"])
            _session["last_to"] = data.get("last_to", _session["last_to"])
            _session["last_delete"] = data.get("last_delete", _session["last_delete"])
            _session["beep_on_complete"] = data.get("beep_on_complete", _session["beep_on_complete"])
            print(r"Loaded: .\data\persistent.json")
    except Exception:
        pass

folder_location = _session["last_folder"]
format_from = _session["last_from"]
format_to = _session["last_to"]
delete_files_after = _session["last_delete"]
beep_on_complete = _session["beep_on_complete"]

# Processing tracking
files_process_done = 0
files_process_total = 0
print("..Initialization Complete.\n")
# ─── Helpers ────────────────────────────────────────────────────────────────────
def save_last_session():
    try:
        DATA_DIR.mkdir(exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps({
                "last_folder": str(Path(folder_location).resolve()),
                "last_from": format_from.upper(),
                "last_to": format_to.upper(),
                "last_delete": bool(delete_files_after),
                "beep_on_complete": bool(beep_on_complete)
            }, indent=2),
            encoding="utf-8"
        )
        print(r"Saved: .\data\persistent.json")
    except Exception as e:
        print(f"Error saving session: {str(e)}")

def set_folder_location(new_location):
    global folder_location
    if new_location and os.path.exists(new_location):
        folder_location = new_location

def set_beep(value):
    global beep_on_complete
    beep_on_complete = bool(value)

def set_delete_files_after(value):
    global delete_files_after
    delete_files_after = bool(value)

def set_format_from(new_format):
    global format_from
    if new_format:
        format_from = new_format.upper()

def set_format_to(new_format):
    global format_to
    if new_format:
        format_to = new_format.upper()

def find_files_to_convert():
    if not os.path.exists(folder_location):
        return []
    files = []
    ext = f".{format_from.lower()}"
    for root, _, filenames in os.walk(folder_location):
        for fn in filenames:
            if fn.lower().endswith(ext):
                files.append(os.path.join(root, fn))
    return files
# ─── ROBUST EXIT HANDLING ───────────────────────────────────────────────────────
def terminate_process_tree(pid=None):
    """Kill all child processes recursively."""
    if pid is None:
        pid = os.getpid()
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except:
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except:
                pass
    except:
        pass

def force_exit_windows():
    """Force exit using Windows API for older Windows versions."""
    try:
        # Use ExitProcess API for clean exit on Windows
        ctypes.windll.kernel32.ExitProcess(0)
    except:
        pass

def graceful_shutdown():
    """
    Robust cross-platform shutdown handler.
    Works on Windows 7/8/8.1/10/11 with multiple fallback strategies.
    """
    global _shutdown_requested, global_demo
    if _shutdown_requested:
        return  # Prevent double execution
    _shutdown_requested = True

    print("\n" + "= "*50)
    print("INITIATING SHUTDOWN SEQUENCE...")
    print("= "*50)

    # Step 1: Save session data
    try:
        save_last_session()
        print("✓ Session saved")
    except Exception as e:
        print(f"! Session save warning: {e}")

    # Step 2: Signal shutdown to prevent new operations
    print("✓ Shutdown flag set")

    # Step 3: Close Gradio interface (async-safe method)
    if global_demo is not None:
        try:
            # Method 1: Try to close the server directly
            if hasattr(global_demo, 'server') and global_demo.server:
                try:
                    global_demo.server.should_exit = True
                    global_demo.server.force_exit = True
                    print("✓ Server exit signaled")
                except:
                    pass
            
            # Method 2: Close the blocks interface
            try:
                global_demo.close()
                print("✓ Interface closed")
            except Exception as e:
                print(f"! Interface close warning: {e}")
                
        except Exception as e:
            print(f"! Gradio cleanup warning: {e}")

    # Step 4: Small delay for cleanup
    time.sleep(0.3)

    # Step 5: Terminate child processes
    terminate_process_tree()
    print("✓ Child processes cleaned")

    # Step 6: OS-specific exit strategy
    print("Executing exit...")

    # Strategy A: Windows-specific force exit (most reliable on Win 7/8)
    if os.name == 'nt':
        try:
            force_exit_windows()
        except:
            pass

    # Strategy B: Standard sys.exit (works on most modern Windows)
    try:
        sys.exit(0)
    except:
        pass

    # Strategy C: os._exit (harsh but effective)
    try:
        os._exit(0)
    except:
        pass

    # Strategy D: Last resort - kill self
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except:
        pass

    # Should never reach here, but just in case
    while True:
        time.sleep(1)

# Register cleanup on normal exit
atexit.register(save_last_session)
# ─── Main Conversion (ASYNC STREAMING) ──────────────────────────────────────────
def start_conversion():
    """
    Generator function for async streaming conversion log.
    Yields progress after each file instead of returning at the end.
    Also yields a short status line for the bottom status bar.
    """
    global files_process_done, files_process_total
    
    if _shutdown_requested:
        yield "Error: Shutdown in progress.", "Shutdown in progress"
        return

    if not os.path.exists(folder_location):
        yield "Error: Invalid folder location.", "Error: Invalid folder"
        return

    files = find_files_to_convert()
    if not files:
        msg = f"No .{format_from.lower()} files found in selected folder."
        yield msg, msg
        return

    files_process_done = 0
    files_process_total = len(files)
    newly_converted = []
    log = [f"Processing {files_process_total} file(s)...\n"]

    # Yield initial status
    yield "\n".join(log), f"Starting conversion of {files_process_total} file(s)..."

    for i, infile in enumerate(files, 1):
        if _shutdown_requested:
            log.append("\n! Shutdown requested, stopping...")
            yield "\n".join(log), "Shutdown requested — stopping"
            break
        
        outfile = os.path.splitext(infile)[0] + f".{format_to.lower()}"
        infile_abs = os.path.abspath(infile)
        outfile_abs = os.path.abspath(outfile)
        working_dir = os.path.dirname(nconvert_path)

        cmd = [
            nconvert_path,
            "-out", format_to.lower(),
            "-overwrite",
            "-o", outfile_abs,
            infile_abs
        ]

        filename_display = os.path.basename(infile)
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                cwd=working_dir,
                timeout=30
            )
            if result.returncode == 0:
                files_process_done += 1
                newly_converted.append(outfile_abs)
                log.append(f"✓ {filename_display} - {format_from.lower()} → {format_to.lower()}")
            else:
                err = result.stderr.strip() or "Unknown error"
                log.append(f"✗ {filename_display} - FAILED ({err})")
        except subprocess.TimeoutExpired:
            log.append(f"⚠ {filename_display} - TIMEOUT")
        except Exception as e:
            log.append(f"✗ {filename_display} - ERROR: {str(e)}")

        # YIELD AFTER EACH FILE for real-time updates
        progress_info = f"\n[{i}/{files_process_total}] Processing..."
        status_line = f"[{i}/{files_process_total}] {filename_display}"
        yield "\n".join(log) + progress_info, status_line

    # Delete originals if requested
    if delete_files_after and not _shutdown_requested:
        deleted_count = 0
        converted_set = set(newly_converted)
        for orig in files:
            if _shutdown_requested:
                break
            expected = os.path.splitext(orig)[0] + f".{format_to.lower()}"
            if expected in converted_set:
                try:
                    os.remove(orig)
                    deleted_count += 1
                except Exception as e:
                    log.append(f"Failed to delete {os.path.basename(orig)}: {e}")
        if deleted_count:
            log.append(f"\nDeleted {deleted_count} original file(s)")
            yield "\n".join(log), f"Deleted {deleted_count} original(s)"

    # Summary
    failed = files_process_total - files_process_done
    log.append("\n" + "─" * 40)
    log.append("CONVERSION SUMMARY")
    log.append(f"Total files:      {files_process_total}")
    log.append(f"Successfully:     {files_process_done}")
    log.append(f"Failed:           {failed}")
    log.append("─" * 40)

    if failed == 0 and files_process_done > 0:
        log.insert(1, "All files converted successfully ✓\n")

    # Beep on completion
    if beep_on_complete and files_process_done > 0 and not _shutdown_requested:
        def delayed_beep():
            time.sleep(0.5)
            if os.name == 'nt':
                winsound.Beep(1000, 800)
            else:
                print("\a")
        Thread(target=delayed_beep, daemon=True).start()

    final_status = f"Done — {files_process_done} ok, {failed} failed"
    yield "\n".join(log), final_status  # FINAL YIELD
# ─── UI ─────────────────────────────────────────────────────────────────────────
def create_interface():
    css = """
    button, .gr-button {
        min-height: 48px !important;
        font-size: 1.05rem !important;
        padding: 0.4rem 0.8rem !important;
    }
    /* Double-height Exit button */
    #exit-btn, #exit-btn button {
        min-height: 96px !important;
        height: 96px !important;
        font-size: 1.25rem !important;
    }
    .gr-row {
        margin-bottom: 0.6rem;
    }
    /* Make the status bar compact */
    #status-bar textarea {
        min-height: 2.2rem !important;
        max-height: 2.2rem !important;
        resize: none !important;
    }
    """
    with gr.Blocks(title="NConvert-Interface", css=css) as demo:
        gr.Markdown("# NConvert-Interface — Image Converter")

        # ─── Main two-column layout ───────────────────────────────────────────
        with gr.Row():
            # LEFT COLUMN — controls
            with gr.Column(scale=1):
                # Row 1: Convert From / Convert To
                with gr.Row():
                    from_dd = gr.Dropdown(
                        choices=allowed_formats,
                        value=format_from,
                        label="Convert From",
                        scale=1
                    )
                    to_dd = gr.Dropdown(
                        choices=allowed_formats,
                        value=format_to,
                        label="Convert To",
                        scale=1
                    )

                # Row 2: Folder Location
                folder_txt = gr.Textbox(
                    label="Folder Location",
                    value=folder_location,
                    placeholder="Select or type folder path...",
                    scale=1
                )

                # Row 3: Delete / Beep toggles (own row)
                with gr.Row():
                    delete_cb = gr.Checkbox(
                        label="Delete originals after",
                        value=delete_files_after,
                        scale=1
                    )
                    beep_cb = gr.Checkbox(
                        label="Beep on completion",
                        value=beep_on_complete,
                        scale=1
                    )

                # Row 4: Browse (left) + Start Conversion (right)
                with gr.Row():
                    browse_btn = gr.Button("Browse", scale=1)
                    convert_btn = gr.Button("Start Conversion", variant="primary", scale=1)

            # RIGHT COLUMN — log only
            with gr.Column(scale=1):
                result_box = gr.Textbox(
                    label="Conversion Log",
                    lines=30,
                    max_lines=30,
                    interactive=False,
                    show_copy_button=True
                )

        # ─── Bottom bar: Status (left/centre) + Exit (far right, double height) ─
        with gr.Row():
            status_box = gr.Textbox(
                label="Status",
                value="Ready",
                interactive=False,
                scale=5,
                elem_id="status-bar"
            )
            exit_btn = gr.Button(
                "Exit",
                variant="stop",
                scale=1,
                elem_id="exit-btn"
            )

        # ─── Event Handlers ─────────────────────────────────────────────────────

        def browse_folder():
            new_folder = filedialog.askdirectory(initialdir=folder_location)
            if new_folder:
                set_folder_location(new_folder)
                return os.path.abspath(new_folder), "", "Folder selected"
            return folder_location, "", "Browse cancelled"

        def change_folder(new_location):
            set_folder_location(new_location)
            return new_location, "", "Folder updated"

        def handle_exit():
            # Run exit in separate thread to avoid blocking Gradio event loop
            exit_thread = Thread(target=graceful_shutdown, daemon=True)
            exit_thread.start()
            # Return immediately to satisfy Gradio's request
            return "Shutting down... The window will close automatically.", "Shutting down..."

        # ─── Bindings ───────────────────────────────────────────────────────────

        browse_btn.click(
            browse_folder,
            outputs=[folder_txt, result_box, status_box]
        )

        folder_txt.change(
            change_folder,
            inputs=folder_txt,
            outputs=[folder_txt, result_box, status_box]
        )

        from_dd.change(set_format_from, inputs=from_dd)
        to_dd.change(set_format_to, inputs=to_dd)
        delete_cb.change(set_delete_files_after, inputs=delete_cb)
        beep_cb.change(set_beep, inputs=beep_cb)

        convert_btn.click(
            fn=start_conversion,
            outputs=[result_box, status_box],
            show_progress=True  # Shows Gradio's built-in progress indicator
        )

        exit_btn.click(
            fn=handle_exit,
            outputs=[result_box, status_box]
        )

    # Enable queue for async streaming support
    # Gradio 3.x: concurrency_count, Gradio 5.x: default_concurrency_limit
    if GRADIO_MAJOR >= 5:
        demo.queue(max_size=10, default_concurrency_limit=1)
    else:
        demo.queue(max_size=10, concurrency_count=1)
    
    return demo
# ─── Built-in Qt Browser ───────────────────────────────────────────────────────
def launch_qt_browser(url, title="NConvert-Interface"):
    """
    Launch an embedded Qt WebEngine browser window pointing at the Gradio UI.
    
    Windows 10+: PyQt6 WebEngine (modern Chromium) + Gradio 5.x
    Windows 8.1: PyQt5 WebEngine (Chromium 83) + Gradio 3.x (compatible JS)
    """
    # ── Try PyQt6 first (Windows 10+), then PyQt5 (Windows 8.1) ──
    QT_VERSION = None
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        from PyQt6.QtCore import QUrl, QTimer
        QT_VERSION = 6
        print("Qt browser: using PyQt6")
    except ImportError:
        try:
            from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
            from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
            from PyQt5.QtCore import QUrl, QTimer
            QT_VERSION = 5
            print("Qt browser: using PyQt5")
        except ImportError:
            print("Warning: No Qt WebEngine available. Falling back to system browser.")
            import webbrowser
            webbrowser.open(url)
            return
    
    # Prevent conflicts: create QApplication only if one doesn't exist
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # ── Compatibility helper for WebEngine settings attributes ──
    def _setting_attr(name):
        """Resolve a QWebEngineSettings attribute by name across Qt5/Qt6."""
        if QT_VERSION == 6:
            return getattr(QWebEngineSettings.WebAttribute, name)
        else:
            return getattr(QWebEngineSettings, name)

    class GradioBrowser(QMainWindow): 
        def __init__(self, url, title):
            super().__init__()
            self.setWindowTitle(title)
            self.resize(1280, 900)
            self.setMinimumSize(800, 600)

            # Central widget & layout
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)

            # WebEngine view
            self.browser = QWebEngineView()
            layout.addWidget(self.browser)

            # Configure web settings (works on both Qt5 and Qt6)
            settings = self.browser.settings()
            settings.setAttribute(_setting_attr("JavascriptEnabled"), True)
            settings.setAttribute(_setting_attr("LocalStorageEnabled"), True)
            settings.setAttribute(_setting_attr("ScrollAnimatorEnabled"), True)
            settings.setAttribute(_setting_attr("PluginsEnabled"), True)

            # Load the Gradio URL
            self.browser.setUrl(QUrl(url))

            # Update window title from page title
            self.browser.titleChanged.connect(self._on_title_changed)

        def _on_title_changed(self, page_title):
            if page_title:
                self.setWindowTitle(f"{page_title} — NConvert-Interface")

        def closeEvent(self, event):
            """When the Qt window is closed, trigger the graceful shutdown."""
            print("Browser window closed — initiating shutdown...")
            event.accept()
            # Schedule shutdown slightly after the window closes
            QTimer.singleShot(200, self._do_shutdown)

        def _do_shutdown(self):
            QApplication.instance().quit()
            # Trigger the Gradio + process shutdown in a thread
            Thread(target=graceful_shutdown, daemon=True).start()

    window = GradioBrowser(url, title)
    window.show()

    # Run the Qt event loop (blocks until window is closed)
    # app.exec() works on both PyQt5 5.15+ and PyQt6
    app.exec()
# ─── Launcher ───────────────────────────────────────────────────────────────────
def find_free_port(start=7860, attempts=12):
    for p in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return None

def close_old_gradio(port):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = ' '.join(proc.info['cmdline'] or [])
            if 'gradio' in cmd.lower() and f"port {port}" in cmd:
                proc.terminate()
        except:
            pass

def launch():
    global global_demo
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer required")
        sys.exit(1)

    port = find_free_port()
    if not port:
        print("No free port found in range 7860–7871")
        sys.exit(1)

    close_old_gradio(port)

    gradio_url = f"http://localhost:{port}"
    print(f"Launching interface on {gradio_url}")
    print(f"OS Version: {WINDOWS_VERSION}")
    print(f"Gradio: {gr.__version__}")

    demo = create_interface()
    global_demo = demo

    # Setup signal handlers for clean exit on Ctrl+C
    def signal_handler(sig, frame):
        print("\nSignal received, shutting down...")
        graceful_shutdown()

    if os.name == 'nt':
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except:
            pass

    # Launch Gradio in a background thread (non-blocking)
    def run_gradio():
        demo.launch(
            server_name="127.0.0.1",
            server_port=port,
            share=False,
            inbrowser=False,
            quiet=False,
            prevent_thread_lock=True  # Non-blocking so Qt can take over the main thread 
        )

    gradio_thread = Thread(target=run_gradio, daemon=True)
    gradio_thread.start()

    # Give Gradio a moment to start up before loading the browser
    time.sleep(2.5)

    # Launch the built-in Qt browser on the main thread (Qt requires main thread)
    launch_qt_browser(gradio_url, title="NConvert-Interface")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    launch()
