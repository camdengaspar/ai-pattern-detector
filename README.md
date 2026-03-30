# AI Pattern Detector

A Python web app that scans text for mechanical AI writing patterns and reports exactly where they appear — formatted for easy handoff to an LLM for revision.

## What It Does

Paste any draft into the text box and click **Analyze**. The scanner checks for 13 common AI writing patterns across three categories and returns an organized report showing:

- **Pattern type** — what kind of AI pattern was detected
- **Location** — which paragraph and sentence it appears in
- **Flagged text** — the exact phrase, shown in context

The **Copy Report** button exports a clean plain-text version of the results, ready to paste into ChatGPT, Claude, or any other LLM with a prompt like: *"Here are the AI writing patterns found in my draft. Please rewrite the flagged passages to remove them."*

## Patterns Detected

### Language & Grammar
| # | Pattern | Signal |
|---|---------|--------|
| 1 | **AI Vocabulary Density** | Overuse of elevated words like "pivotal", "delve", "tapestry", "meticulous" |
| 2 | **Copulative Avoidance** | "serves as", "stands as", "marks" replacing plain "is/are" |
| 3 | **Negative Parallelism — Not Just…But** | "Not only does it X, but it also Y" constructions |
| 4 | **Negative Parallelism — Not X…But Y** | "It's not X. It's Y." / "X, not the Y." negation-then-affirmation |
| 5 | **Rule of Three** | Compulsive three-item lists of adjectives or phrases |
| 6 | **Elegant Variation** | Synonym cycling — "the entrepreneur", "the executive", "the business leader" for the same subject |

### Style
| # | Pattern | Signal |
|---|---------|--------|
| 7 | **Title Case Section Headings** | Every Main Word Capitalized Instead of Sentence case |
| 8 | **Mechanical Bolding** | Bolding every keyword rather than using bold for genuine emphasis |
| 9 | **Emoji in Structural Elements** | Emoji decorating headings or bullet points |
| 10 | **Em Dash Overuse** | Em dashes (—) where a comma or colon would be more natural |
| 11 | **Unnecessary Tables** | Small 2–4 row tables for data that could be one sentence |

### Additional
| # | Pattern | Signal |
|---|---------|--------|
| 12 | **Sycophantic Opener** | "Great question!", "Absolutely!", "Certainly!" before actually answering |
| 13 | **Formulaic Conclusion** | "In summary…" / "In conclusion…" recap to close |

Hover over the **?** icon next to any pattern name in the UI for a plain-English definition and examples.

## Getting Started

### Option 1 — Browser (no install)
Just open `index.html` in any browser. No server, no dependencies.

```bash
open index.html
```

### Option 2 — Flask (local server)

**Requirements:** Python 3.8+

```bash
# Clone the repo
git clone https://github.com/camdengaspar/ai-pattern-detector.git
cd ai-pattern-detector/flask-version

# Create a virtual environment and install dependencies
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Run the app
venv/bin/python3 app.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Project Structure

```
ai-pattern-detector/
├── index.html              # Standalone JS version — open in any browser or deploy to GitHub Pages
├── README.md
└── flask-version/          # Original Python/Flask app (local development)
    ├── app.py              # Flask app — serves the UI and /analyze endpoint
    ├── detector.py         # All 13 pattern detectors and location-mapping logic
    ├── requirements.txt    # Python dependencies (flask only)
    └── templates/
        └── index.html      # Flask frontend
```

## How Detection Works

All detection is pure regex and string analysis — no ML models or external APIs. Each pattern scans the submitted text and a location-mapping helper converts character offsets to human-readable `Paragraph N, Sentence M` labels so results are easy to find in the original draft.

The JS version (`index.html`) runs entirely in the browser. The Flask version (`flask-version/`) runs the same logic in Python on a local server, with findings returned as JSON to the frontend.

## Notes

- No single pattern proves AI authorship — these signals are most meaningful in combination.
- The detector is tuned to minimize false positives for common human writing constructs (e.g., product feature lists, long enumeration lists, standalone negations without affirmations).
- Detection patterns are based on the Language & Grammar and Style sections of Wikipedia's [Signs of AI Writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).
