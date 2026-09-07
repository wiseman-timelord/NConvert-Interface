# script: installer.py
"""
NConvert-Interface Installer
Handles all installation requirements for NConvert-Interface application
"""
import os
import sys
import subprocess
import platform
import zipfile
import shutil
import urllib.request
import urllib.error
from pathlib import Path
import tempfile
import time
import json
import configparser

# Global Constants
NCONVERT_URLS = {  # Download URLs for NConvert
    'x64': 'https://download.xnview.com/NConvert-win64.zip',
    'x32': 'https://download.xnview.com/NConvert-win.zip'
}

# Base application packages (direct dependencies only — NOT Gradio transitive deps)
# Gradio pulls in its own dependency tree; pinning those causes version conflicts
# between Gradio 3.x (Win 8.1) and Gradio 5.x (Win 10+)
INSTALL_PACKAGES_BASE = [
    "psutil>=5.9.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0,<2",
    "pillow>=10.0.0",
]

# Gradio version depends on OS:
#   Win 8.1 → Gradio 3.50.2 (JS works with Qt5 WebEngine / Chromium 83)
#   Win 10+ → Gradio 5.49.1 (needs modern Chromium, Qt6 WebEngine provides it)
GRADIO_WIN81 = "gradio==3.50.2"
GRADIO_WIN10 = "gradio==5.49.1"

# PyQt6 packages — requires Windows 10+ (Qt 6 dropped Win 7/8/8.1 entirely)
INSTALL_PACKAGES_PYQT6 = [
    "PyQt6>=6.5.0",
    "PyQt6-WebEngine>=6.5.0",
]

# PyQt5 packages — for Windows 8.1 and older (Qt 5.15 supports Win 7/8/8.1)
INSTALL_PACKAGES_PYQT5 = [
    "PyQt5>=5.15.0,<5.16.0",
    "PyQtWebEngine>=5.15.0,<5.16.0",
]

# Critical packages for verification (subset of installed packages)
CRITICAL_PACKAGES_BASE = ['gradio', 'psutil']

PACKAGE_IMPORT_MAP = {  # Map package names to import names for verification
    'gradio': 'gradio',
    'psutil': 'psutil',
    'PyQt6-WebEngine': 'PyQt6.QtWebEngineWidgets',
    'PyQtWebEngine': 'PyQt5.QtWebEngineWidgets',
}

MIN_PYTHON_VERSION = (3, 10)  # Minimum required Python version (Gradio 5.x needs 3.10+)
SEPARATOR_LENGTH = 79
HEADER_CHAR = "="
SEPARATOR_CHAR = "-"
MAX_RETRIES = 4           # slightly more forgiving
RETRY_DELAY = 4           # give server/network more time to recover

# Default settings for persistent.json
DEFAULT_SESSION = {
    "last_folder": str(Path(__file__).parent.resolve() / "temp"),
    "last_from": "PSPIMAGE",
    "last_to": "JPEG",
    "last_delete": False,
    "beep_on_complete": False
}

class NConvertInstaller:
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.data_dir = self.script_dir / "data"
        self.nconvert_dir = self.data_dir / "NConvert"
        self.nconvert_exe = self.nconvert_dir / "nconvert.exe"
        self.session_file = self.data_dir / "persistent.json"
        self.constants_file = self.data_dir / "constants.ini"
        self.workspace_dir = self.script_dir / "temp"
        self.venv_dir = self.script_dir / "VENV"
        self.venv_python = self.venv_dir / "Scripts" / "python.exe"

        # Detect OS and build conditional package/verification lists
        self.win_version = self._detect_windows_version()
        self.pyqt6_supported = self._is_pyqt6_supported()
        self.gradio_version = GRADIO_WIN10 if self.pyqt6_supported else GRADIO_WIN81
        self.pyqt_packages = INSTALL_PACKAGES_PYQT6 if self.pyqt6_supported else INSTALL_PACKAGES_PYQT5
        self.critical_packages = self._build_critical_packages()

    @staticmethod
    def _detect_windows_version():
        """Detect Windows version string for compatibility decisions."""
        if os.name != 'nt':
            return None
        ver = sys.getwindowsversion()
        if ver.major == 6:
            if ver.minor == 1:
                return "win7"
            elif ver.minor == 2:
                return "win8"
            elif ver.minor == 3:
                return "win81"
        elif ver.major == 10:
            if ver.build >= 22000:
                return "win11"
            return "win10"
        return "unknown"

    def _is_pyqt6_supported(self):
        """Qt 6 (all versions) requires Windows 10 or later."""
        if self.win_version is None:
            return False  # Non-Windows: skip PyQt6 (Linux/Mac would need separate handling)
        return self.win_version in ("win10", "win11")

    def _build_critical_packages(self):
        """Build the verification list: base + correct Qt WebEngine."""
        packages = list(CRITICAL_PACKAGES_BASE)
        if self.pyqt6_supported:
            packages.append('PyQt6-WebEngine')
        else:
            packages.append('PyQtWebEngine')
        return packages

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self, title, char=None, length=None):
        char = char or HEADER_CHAR
        length = length or SEPARATOR_LENGTH
        separator = char * length
        print(f"{separator}")
        print(f"    {title}")
        print(f"{separator}\n")

    def print_separator(self, char=None, length=None):
        char = char or SEPARATOR_CHAR
        length = length or SEPARATOR_LENGTH
        print(char * length)

    def print_status(self, message, success=True):
        symbol = "✓" if success else "✗"
        print(f"{symbol} {message}")

    def check_python_version(self):
        current_version = sys.version_info[:2]
        if current_version < MIN_PYTHON_VERSION:
            self.print_status(
                f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required, "
                f"found {current_version[0]}.{current_version[1]}",
                success=False
            )
            return False
        self.print_status(f"Python {current_version[0]}.{current_version[1]} detected")
        return True

    def detect_architecture(self):
        """Auto-detect system architecture and return 'x64' or 'x32'."""
        machine = platform.machine().lower()
        architecture = platform.architecture()[0]

        if machine in ['amd64', 'x86_64'] or architecture == '64bit':
            detected = 'x64'
        elif machine in ['i386', 'i686', 'x86'] or architecture == '32bit':
            detected = 'x32'
        else:
            detected = 'x64'  # default assumption

        arch_label = "64-bit" if detected == 'x64' else "32-bit"
        print(f"Detected architecture: {arch_label} ({detected}) "
              f"[machine={machine}, platform.architecture={architecture}]")
        return detected

    def create_workspace(self):
        try:
            self.workspace_dir.mkdir(exist_ok=True)
            self.print_status(f"Workspace directory ready: {self.workspace_dir}")
            return True
        except Exception as e:
            self.print_status(f"Failed to create workspace directory: {e}", success=False)
            return False

    def create_venv(self):
        """Create a virtual environment at .\\VENV using system Python."""
        if self.venv_python.exists():
            self.print_status(f"Virtual environment already exists at .\\VENV\\")
            return True

        print(f"Creating virtual environment at .\\VENV\\...")
        print(f"  Using system Python: {sys.executable}")
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'venv', str(self.venv_dir)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                self.print_status("Failed to create virtual environment", success=False)
                if result.stderr:
                    print(result.stderr.strip())
                return False

            if not self.venv_python.exists():
                self.print_status("venv created but python.exe not found inside", success=False)
                return False

            self.print_status(f"Virtual environment created at .\\VENV\\")
            return True
        except Exception as e:
            self.print_status(f"Failed to create virtual environment: {e}", success=False)
            return False

    def purge_venv(self):
        """Remove the entire .\\VENV\\ directory for a clean install."""
        if self.venv_dir.exists():
            print(f"Purging virtual environment: {self.venv_dir}")
            try:
                shutil.rmtree(self.venv_dir)
                self.print_status("Virtual environment removed")
            except Exception as e:
                self.print_status(f"Failed to remove virtual environment: {e}", success=False)
                return False
        else:
            print("Virtual environment does not exist, nothing to purge.")
        return True

    def download_file(self, url, destination):
        retry_count = 0
        local_size = 0

        if destination.exists():
            local_size = destination.stat().st_size
            print(f"Found partial download ({local_size / (1024*1024):.1f} MB) → will attempt to resume")

        while retry_count < MAX_RETRIES:
            try:
                req = urllib.request.Request(url)
                if local_size > 0:
                    req.add_header("Range", f"bytes={local_size}-")

                attempt_type = "Resuming" if local_size > 0 else "Starting"
                print(f"\nDownload attempt {retry_count + 1}/{MAX_RETRIES} - {attempt_type} download...")

                with urllib.request.urlopen(req, timeout=30) as response:
                    total_size = int(response.getheader('Content-Length', 0)) + local_size
                    mode = 'ab' if local_size > 0 else 'wb'

                    with open(destination, mode) as f:
                        downloaded_bytes = local_size
                        while True:
                            chunk = response.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded_bytes += len(chunk)

                            if total_size > 0:
                                percent = (downloaded_bytes * 100) // total_size
                                mb_downloaded = downloaded_bytes / (1024 * 1024)
                                print(f"\rProgress: {percent:3d}%  ({mb_downloaded:6.1f}/{total_size/(1024*1024):.1f} MB)", end='')
                            else:
                                print(f"\rDownloaded: {downloaded_bytes/(1024*1024):.1f} MB", end='')

                    print()  # final newline

                    # Final size check
                    final_size = destination.stat().st_size
                    if total_size > 0 and final_size != total_size:
                        print(f"\nIncomplete download detected ({final_size} / {total_size} bytes)")
                        raise ConnectionError("Download incomplete")

                    print("Download completed successfully ✓")
                    return True

            except Exception as e:
                print(f"\nDownload failed: {str(e)}")
                retry_count += 1

                if retry_count < MAX_RETRIES:
                    # Do NOT delete partial file when retrying - we want to resume
                    print(f"Retrying in {RETRY_DELAY} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                    time.sleep(RETRY_DELAY)
                    # Update local_size for next resume attempt
                    if destination.exists():
                        local_size = destination.stat().st_size
                else:
                    # Only on final failure do we clean up
                    print("Maximum retries reached. Cleaning up partial file...")
                    destination.unlink(missing_ok=True)
                    return False

        return False

    def extract_zip(self, zip_path, extract_to):
        try:
            print(f"Extracting: {zip_path.name}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if zip_ref.testzip() is not None:
                    self.print_status("Corrupted ZIP file", success=False)
                    return False
                zip_ref.extractall(extract_to)
            self.print_status("Extraction completed")
            return True
        except Exception as e:
            self.print_status(f"Extraction error: {e}", success=False)
            return False

    def move_nconvert_files(self, source_dir):
        """Move NConvert files into .\\data\\NConvert\\"""
        nconvert_extracted = source_dir / "NConvert"
        if not nconvert_extracted.exists():
            self.print_status("NConvert directory not found in extracted files", success=False)
            return False
        try:
            # Ensure target directory exists
            self.nconvert_dir.mkdir(parents=True, exist_ok=True)

            moved_count = 0
            for item in nconvert_extracted.iterdir():
                destination = self.nconvert_dir / item.name
                if destination.exists():
                    if destination.is_file():
                        destination.unlink()
                    else:
                        shutil.rmtree(destination)
                shutil.move(str(item), str(destination))
                moved_count += 1
                print(f"Moved: {item.name}")
            if nconvert_extracted.exists():
                nconvert_extracted.rmdir()
            self.print_status(f"Moved {moved_count} items to .\\data\\NConvert\\")
            return True
        except Exception as e:
            self.print_status(f"Error moving files: {e}", success=False)
            return False

    def install_nconvert(self):
        if self.nconvert_exe.exists():
            self.print_status(f"nconvert.exe already exists at .\\data\\NConvert\\")
            return True
        
        print("NConvert not found, attempting download...")
        architecture = self.detect_architecture()
        url = NCONVERT_URLS[architecture]
        arch_label = "64-bit" if architecture == 'x64' else "32-bit"
        print(f"Downloading NConvert {arch_label} from: {url}")
        
        # Better naming for temp file (easier to recognize when debugging)
        with tempfile.NamedTemporaryFile(suffix='.zip', prefix='nconvert-', delete=False) as tmp:
            zip_path = Path(tmp.name)

        success = self.download_file(url, zip_path)

        if not success:
            zip_path.unlink(missing_ok=True)
            return False

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            if not self.extract_zip(zip_path, temp_path):
                zip_path.unlink(missing_ok=True)
                return False
            if not self.move_nconvert_files(temp_path):
                zip_path.unlink(missing_ok=True)
                return False

        zip_path.unlink(missing_ok=True)
        
        if self.nconvert_exe.exists():
            self.print_status("NConvert installation completed")
            return True
        else:
            self.print_status("nconvert.exe not found after installation", success=False)
            return False

    def install_python_packages(self):
        """Install all packages into the .\\VENV\\ virtual environment.
        
        Installs in 3 stages to avoid dependency conflicts:
          1. Base direct dependencies (psutil, pandas, numpy, pillow)
          2. Gradio (OS-specific version — pip resolves its own dep tree)
          3. PyQt + WebEngine (OS-specific — Qt5 for Win 8.1, Qt6 for Win 10+)
        """
        venv_py = str(self.venv_python)
        gradio_label = self.gradio_version.split("==")[1]
        qt_label = "PyQt5/Qt5" if not self.pyqt6_supported else "PyQt6/Qt6"

        print(f"\nDetected: {self.win_version}")
        print(f"  Gradio {gradio_label}, {qt_label} WebEngine")
        print(f"  Target: {venv_py}")

        # ── Stage 0: Upgrade pip ──
        print("\nUpgrading pip inside virtual environment...")
        result = subprocess.run(
            [venv_py, '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            self.print_status("pip and setuptools upgraded in VENV")
        else:
            self.print_status("Failed to upgrade pip/setuptools in VENV", success=False)
            if result.stderr:
                print(result.stderr.strip())
            return False

        # ── Stage 1: Base direct dependencies ──
        print("\nInstalling base application packages...")
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as req_file:
            req_file.write("\n".join(INSTALL_PACKAGES_BASE))
            req_file_path = Path(req_file.name)
        try:
            result = subprocess.run(
                [venv_py, '-m', 'pip', 'install', '-r', str(req_file_path)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.print_status("Base packages installed")
            else:
                self.print_status("Failed to install base packages", success=False)
                if result.stderr:
                    print(result.stderr.strip())
                return False
        finally:
            req_file_path.unlink(missing_ok=True)

        # ── Stage 2: Gradio (OS-specific version) ──
        print(f"\nInstalling Gradio {gradio_label}...")
        result = subprocess.run(
            [venv_py, '-m', 'pip', 'install', self.gradio_version],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            self.print_status(f"Gradio {gradio_label} installed")
        else:
            self.print_status(f"Failed to install Gradio {gradio_label}", success=False)
            if result.stderr:
                print(result.stderr.strip())
            return False

        # ── Stage 3: PyQt + WebEngine (OS-specific) ──
        print(f"\nInstalling {qt_label} WebEngine (built-in browser)...")
        for pkg in self.pyqt_packages:
            result = subprocess.run(
                [venv_py, '-m', 'pip', 'install', pkg],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.print_status(f"{pkg.split('>=')[0]} installed")
            else:
                self.print_status(f"Failed to install {pkg}", success=False)
                if result.stderr:
                    print(result.stderr.strip())
                return False

        self.print_status("All application packages installed successfully")
        return True

    def create_default_session_file(self):
        try:
            self.data_dir.mkdir(exist_ok=True)
            self.session_file.write_text(
                json.dumps(DEFAULT_SESSION, indent=2),
                encoding="utf-8"
            )
            self.print_status(f"Default persistent config created: data/persistent.json")
            return True
        except Exception as e:
            self.print_status(f"Could not create persistent config: {e}", success=False)
            return False

    def create_constants_ini(self):
        """Write detected system constants to data/constants.ini.

        Values stored:
          [system]
          os_version      – win81 | win10 | win11 | ...
          python_version  – e.g. 3.12
          working_directory – absolute path to the script/batch directory
        """
        try:
            self.data_dir.mkdir(exist_ok=True)
            cfg = configparser.ConfigParser()
            cfg["system"] = {
                "os_version": self.win_version or "unknown",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "working_directory": str(self.script_dir),
            }
            with open(self.constants_file, "w", encoding="utf-8") as f:
                cfg.write(f)
            self.print_status(f"System constants written: data/constants.ini")
            return True
        except Exception as e:
            self.print_status(f"Could not create constants.ini: {e}", success=False)
            return False

    def verify_installation(self):
        print("\nVerifying critical components...")
        all_good = True

        if self.nconvert_exe.exists():
            self.print_status(f"nconvert.exe found at .\\data\\NConvert\\")
        else:
            self.print_status("nconvert.exe missing", success=False)
            all_good = False

        if not self.venv_python.exists():
            self.print_status("VENV python.exe not found — venv may be corrupted", success=False)
            return False

        venv_py = str(self.venv_python)
        for package_name in self.critical_packages:
            import_name = PACKAGE_IMPORT_MAP.get(package_name, package_name.replace('-', '_'))
            try:
                subprocess.run(
                    [venv_py, '-c', f'import {import_name}; print("{import_name} OK")'],
                    capture_output=True, text=True, timeout=8, check=True
                )
                self.print_status(f"{package_name} available")
            except Exception as e:
                self.print_status(f"{package_name} verification failed: {str(e)}", success=False)
                all_good = False

        if not self.pyqt6_supported:
            print(f"  (Using PyQt5/Qt 5.15 for {self.win_version or 'this OS'} compatibility)")

        if all_good:
            self.print_status("All critical components verified successfully")
        else:
            self.print_status("Some critical components failed verification", success=False)
        
        return all_good

    # ─── Clean Install ──────────────────────────────────────────────────────────

    def purge_data_directory(self):
        """Remove the entire .\\data\\ directory for a clean install."""
        if self.data_dir.exists():
            print(f"Purging data directory: {self.data_dir}")
            try:
                shutil.rmtree(self.data_dir)
                self.print_status("Data directory removed")
            except Exception as e:
                self.print_status(f"Failed to remove data directory: {e}", success=False)
                return False
        else:
            print("Data directory does not exist, nothing to purge.")

        # Also remove workspace temp directory
        if self.workspace_dir.exists():
            print(f"Purging workspace directory: {self.workspace_dir}")
            try:
                shutil.rmtree(self.workspace_dir)
                self.print_status("Workspace directory removed")
            except Exception as e:
                self.print_status(f"Failed to remove workspace directory: {e}", success=False)
                return False

        return True

    def uninstall_python_packages(self):
        """Remove the virtual environment for a clean slate (replaces per-package uninstall)."""
        print("\nRemoving virtual environment for clean reinstall...")
        return self.purge_venv()

    # ─── Installation Flows ─────────────────────────────────────────────────────

    def run_regular_install(self):
        """Regular Install / Refresh: install or update everything in-place."""
        self.clear_screen()
        self.print_header("NConvert-Interface — Regular Install / Refresh")

        if not self.check_python_version():
            return False

        if not self.create_workspace():
            return False

        if not self.install_nconvert():
            return False

        if not self.create_venv():
            return False

        if not self.install_python_packages():
            return False

        if not self.create_default_session_file():
            return False

        if not self.create_constants_ini():
            return False

        success = self.verify_installation()

        print("\n" + "=" * SEPARATOR_LENGTH)
        if success:
            print("✓ Installation completed successfully!")
            print("\nYou can now run NConvert-Interface.bat")
        else:
            print("✗ Installation encountered issues")
            print("Please review the messages above")

        return success

    def run_clean_install(self):
        """Clean Install: purge everything in .\\data\\, .\\temp\\, and .\\VENV\\, then reinstall."""
        self.clear_screen()
        self.print_header("NConvert-Interface — Clean Install")

        if not self.check_python_version():
            return False

        print()
        
        # Purge phase
        self.print_header("Phase 1: Purge", char="-")
        if not self.purge_data_directory():
            return False
        if not self.uninstall_python_packages():
            return False

        # Install phase
        self.print_header("Phase 2: Fresh Install", char="-")
        if not self.create_workspace():
            return False

        if not self.install_nconvert():
            return False

        if not self.create_venv():
            return False

        if not self.install_python_packages():
            return False

        if not self.create_default_session_file():
            return False

        if not self.create_constants_ini():
            return False

        success = self.verify_installation()

        print("\n" + "=" * SEPARATOR_LENGTH)
        if success:
            print("✓ Clean installation completed successfully!")
            print("\nYou can now run NConvert-Interface.bat")
        else:
            print("✗ Installation encountered issues")
            print("Please review the messages above")

        return success

    # ─── Installer Menu ─────────────────────────────────────────────────────────

    def show_menu(self):
        """Display the installer menu and return the user's choice."""
        self.clear_screen()
        self.print_header("NConvert-Interface Installer")
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print("     1. Regular Install / Refresh")
        print("        Install or update all components in-place.")
        print()
        print("     2. Clean Install")
        print("        Purge .\\data\\, .\\temp\\, and .\\VENV\\, then reinstall fresh.")
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        print()
        self.print_separator()

        while True:
            choice = input("Selection; Menu Options = 1-2, Exit Installer = X: ").strip()
            if choice in ("1", "2") or choice.upper() == "X":
                return choice.upper()
            else:
                print("Invalid option. Please try again.")


def main():
    installer = NConvertInstaller()
    try:
        choice = installer.show_menu()

        if choice == "1":
            success = installer.run_regular_install()
        elif choice == "2":
            success = installer.run_clean_install()
        elif choice == "X":
            print("\nExiting installer.")
            sys.exit(0)
        else:
            success = False

        print("\nPress Enter to exit...")
        input()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print("Unexpected error during installation:")
        print(str(e))
        print("\nPress Enter to exit...")
        input()
        sys.exit(1)

if __name__ == "__main__":
    main()
