from flask import Flask, request, jsonify, render_template
from statistics import main, export_data
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get-data", methods=["POST"])
def get_data_route():
    payload = request.get_json()
    print("Payload:", payload)

    mode = payload.get("mode")

    if mode == "12h":
        date = payload.get("date")
        start_hour = payload.get("start_hour")

        if not date:
            return jsonify({"error": "Missing date"}), 400

        if start_hour is None:
            return jsonify({"error": "Missing start_hour"}), 400

        start_hour = int(start_hour)

        time_from_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=start_hour)
        time_to_dt = time_from_dt + timedelta(hours=12)

    elif mode == "day":
        date = payload.get("date")

        if not date:
            return jsonify({"error": "Missing date"}), 400

        time_from_dt = datetime.strptime(date, "%Y-%m-%d")
        time_to_dt = time_from_dt + timedelta(days=1)

    elif mode == "custom":
        date_from = payload.get("date_from")
        date_to = payload.get("date_to")

        if not date_from or not date_to:
            return jsonify({"error": "Missing custom dates"}), 400

        time_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        time_to_dt = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)

    else:
        return jsonify({"error": "Invalid mode"}), 400

    time_from = time_from_dt.strftime("%Y-%m-%d %H:%M:%S")
    time_to = time_to_dt.strftime("%Y-%m-%d %H:%M:%S")

    print("Using time range:", time_from, "to", time_to)

    segments = main(
        time_from=time_from,
        time_to=time_to,
        altitude_from=0,
        altitude_to=38000
    )

    result = export_data(segments)

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
