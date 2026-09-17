from flask import Flask, jsonify, render_template
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

SIH_URL = "https://sih.gov.in/sih2026PS"

TARGET_PS = "26089"
TARGET_SUBMISSIONS = 500

# Store the latest successfully fetched data in memory.
data_cache = {
    "problem_statements": [],
    "last_fetched": None,
    "error": None
}


def fetch_sih_data():
    """
    Fetch and extract Problem Statement submission data
    from the SIH website.
    """

    response = requests.get(
        SIH_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            )
        },
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    for row in soup.select("#dataTablePS tbody > tr"):

        link = row.select_one(
            "[data-target^='#ViewProblemStatement']"
        )

        if not link:
            continue

        target = link.get("data-target", "")

        match = re.search(
            r"ViewProblemStatement(\d+)",
            target
        )

        if not match:
            continue

        problem_id = match.group(1)

        cells = row.find_all(
            "td",
            recursive=False
        )

        if len(cells) < 6:
            continue

        submitted_text = cells[5].get_text(
            " ",
            strip=True
        )

        # Extract numeric value.
        submitted_match = re.search(
            r"[\d,]+",
            submitted_text
        )

        if submitted_match:
            submitted = int(
                submitted_match.group(0)
                .replace(",", "")
            )
        else:
            submitted = 0

        results.append({
            "id": problem_id,
            "submitted": submitted
        })

    # Sort by submissions in ascending order.
    results.sort(
        key=lambda x: x["submitted"]
    )

    return results


def update_cache():
    """
    Fetch fresh data and update the server-side cache.
    """

    try:

        results = fetch_sih_data()

        # Current time in India.
        now = datetime.now(
            ZoneInfo("Asia/Kolkata")
        )

        data_cache["problem_statements"] = results
        data_cache["last_fetched"] = now.isoformat()
        data_cache["error"] = None

        return True, None

    except Exception as exc:

        data_cache["error"] = str(exc)

        return False, str(exc)


@app.route("/")
def index():
    """
    Serve the dashboard.
    """

    return render_template("index.html")


@app.route("/api/data")
def api_data():
    """
    Return the currently cached dashboard data.
    """

    results = data_cache["problem_statements"]

    target = next(
        (
            item
            for item in results
            if item["id"] == TARGET_PS
        ),
        None
    )

    ps89_submissions = (
        target["submitted"]
        if target
        else 0
    )

    percentage = (
        ps89_submissions /
        TARGET_SUBMISSIONS
    ) * 100

    return jsonify({
        "success": True,

        "target_ps": TARGET_PS,

        "target_submissions":
            TARGET_SUBMISSIONS,

        "ps89_submissions":
            ps89_submissions,

        "ps89_percentage":
            round(percentage, 2),

        "total_problem_statements":
            len(results),

        "problem_statements":
            results,

        "last_fetched":
            data_cache["last_fetched"],

        "error":
            data_cache["error"]
    })


@app.route("/api/refresh", methods=["POST"])
def refresh():
    """
    Force a fresh fetch from SIH.
    """

    success, error = update_cache()

    if not success:

        return jsonify({
            "success": False,
            "error": error,
            "last_fetched":
                data_cache["last_fetched"]
        }), 502

    return jsonify({
        "success": True,
        "message": "SIH data refreshed successfully.",
        "last_fetched":
            data_cache["last_fetched"]
    })

update_cache()

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
    )