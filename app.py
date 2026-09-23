from flask import Flask, request, jsonify, session, render_template, redirect
import csv
import io
import json
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
COMMON_PASSWORD = os.environ.get("COMMON_PASSWORD", "leave123")

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def load():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(x):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(x, f, ensure_ascii=False, indent=2)


def parse(f):
    t = f.read().decode("utf-8-sig", errors="replace")
    delim = "\t" if "\t" in t[:10000] else ","
    rs = list(csv.reader(io.StringIO(t), delimiter=delim))

    hi = next(
        (
            i for i, r in enumerate(rs[:30])
            if any(
                "employee" in x.lower() and "id" in x.lower()
                for x in r
            )
            or any(x.strip().upper() == "ID" for x in r)
        ),
        0
    )

    hs = [x.strip() or f"Column {i+1}" for i, x in enumerate(rs[hi])]

    ik = next(
        (
            h for h in hs
            if h.strip().upper() == "ID"
            or ("employee" in h.lower() and "id" in h.lower())
        ),
        None
    )

    if not ik:
        raise ValueError("Employee ID column not found")

    out = {}

    for r in rs[hi + 1:]:
        if not any(x.strip() for x in r):
            continue

        r = r + [""] * max(0, len(hs) - len(r))
        d = {hs[i]: r[i].strip() for i in range(len(hs))}

        if d.get(ik, "").strip():
            out[d[ik].strip()] = d

    return list(out.values())


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/admin")
def admin():
    return render_template("admin.html")


@app.get("/api/status")
def status():
    return jsonify(
        logged_in=bool(session.get("admin")),
        total=len(load())
    )


@app.post("/api/access")
def access_login():
    p = (request.get_json(silent=True) or {}).get("password", "")

    if p == COMMON_PASSWORD:
        session["employee_access"] = True
        return jsonify(ok=True)

    return jsonify(ok=False, error="Wrong password"), 401


@app.post("/api/access/logout")
def access_logout():
    session.pop("employee_access", None)
    return jsonify(ok=True)


@app.post("/api/login")
def login():
    p = (request.get_json(silent=True) or {}).get("password", "")

    if p == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify(ok=True, total=len(load()))

    return jsonify(ok=False, error="Wrong password"), 401


@app.post("/api/logout")
def logout():
    session.pop("admin", None)
    return jsonify(ok=True)


@app.get("/api/search")
def search():
    if not session.get("employee_access"):
        return jsonify(ok=False, error="Please enter the portal password first"), 401

    eid = request.args.get("employee_id", "").strip().lower()

    if not eid:
        return jsonify(ok=False, error="Employee ID is required"), 400

    for r in load():
        if str(r.get("ID", "")).strip().lower() == eid:
            return jsonify(ok=True, employee=r)

    return jsonify(ok=False, error="Employee ID not found"), 404


@app.post("/api/upload")
def upload():
    if not session.get("admin"):
        return jsonify(ok=False, error="Please login first"), 401

    f = request.files.get("file")

    if not f:
        return jsonify(ok=False, error="Select a file"), 400

    try:
        x = parse(f)

        if not x:
            return jsonify(ok=False, error="No employee records found"), 400

        # New upload completely replaces the old leave data.
        save(x)

        return jsonify(
            ok=True,
            total=len(x),
            message="Upload successful. Old data replaced."
        )

    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
