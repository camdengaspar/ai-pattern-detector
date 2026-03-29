from flask import Flask, render_template, request, jsonify
import detector

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    text = data.get("text", "")
    findings = detector.analyze(text)

    # Group by category for the response
    grouped = {}
    for f in findings:
        cat = f["category"]
        if cat not in grouped:
            grouped[cat] = {}
        pt = f["pattern_type"]
        if pt not in grouped[cat]:
            grouped[cat][pt] = []
        grouped[cat][pt].append({
            "location": f["location"],
            "matched_text": f["matched_text"],
            "context": f["context"],
        })

    return jsonify({
        "total_findings": len(findings),
        "patterns_triggered": sum(len(v) for v in grouped.values()),
        "grouped": grouped,
        "flat": findings,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
