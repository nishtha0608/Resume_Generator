import io
import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(override=True)

from resume_builder import generate_resume

# ---------------------------------------------------------------------------
# App setup — serve frontend/ as static files at /
# ---------------------------------------------------------------------------

_frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app = Flask(__name__, static_folder=_frontend_dir, static_url_path="")

CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
    }
})

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request validation helper
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["name", "country"]  # email, job_description are optional

def _validate_request(data: dict) -> list[str]:
    """Return a list of validation error messages. Empty list = valid."""
    errors = []
    for field in REQUIRED_FIELDS:
        if not data.get(field, "").strip():
            errors.append(f"'{field}' is required.")
    valid_countries = ["USA", "Canada", "India", "Australia"]
    if data.get("country") and data["country"] not in valid_countries:
        errors.append(f"'country' must be one of: {', '.join(valid_countries)}")
    return errors



@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return "", 204


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ATS Resume Generator API"})


@app.route("/generate-resume", methods=["POST"])
def generate():

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    errors = _validate_request(data)
    if errors:
        return jsonify({"error": "Validation failed.", "details": errors}), 422

    logger.info(f"Generating resume for: {data.get('name')} | Country: {data.get('country')}")

    try:
        result = generate_resume(data)
        return jsonify(result), 200
    except RuntimeError as e:
        logger.error(f"Generation error: {e}")
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.exception("Unexpected error during resume generation")
        return jsonify({"error": "Internal server error.", "details": str(e)}), 500



@app.route("/download-pdf", methods=["POST"])
def download_pdf():

    data = request.get_json(silent=True)
    if not data or not data.get("html"):
        return jsonify({"error": "Missing 'html' field."}), 400

    try:
        from weasyprint import HTML, CSS

        html_content = data["html"]
        filename = data.get("filename", "resume.pdf")

        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
</style>
</head>
<body>{html_content}</body>
</html>"""

        pdf_bytes = HTML(string=full_html).write_pdf()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@app.route("/check-openai", methods=["GET"])
@app.route("/check-ollama", methods=["GET"])
def check_ai():
    import os
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or not key.startswith("sk-"):
        return jsonify({"available": False, "error": "OPENAI_API_KEY not set in .env"})
    return jsonify({"available": True, "model": "gpt-4o-mini"})


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ATS Resume Generator — Backend API")
    print("  Running at: http://localhost:5001")
    print("  Docs: GET /  |  Generate: POST /generate-resume")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=True)

