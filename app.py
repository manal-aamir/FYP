import json
import os
from typing import Optional
from io import BytesIO
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
from docx import Document
from acroynom import expand_acronyms, load_abbreviations
from citations import detect_citation_style, format_citation

load_dotenv()

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing in .env")

app = Flask(__name__)

# Instantiate the modern Google GenAI client once and reuse it.
MODEL_NAME = "gemini-2.0-flash"
GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)

REQUIREMENTS_PATH = os.path.join(os.path.dirname(__file__), "requirements.md")

def load_requirements_text() -> str:
    if not os.path.exists(REQUIREMENTS_PATH):
        raise FileNotFoundError(f"requirements.md not found at {REQUIREMENTS_PATH}")
    with open(REQUIREMENTS_PATH, "r", encoding="utf-8") as file:
        return file.read()


REQUIREMENTS_TEXT = load_requirements_text()

CITATION_STYLES = [
    "apa", "ieee", "mla", "chicago", "harvard",
    "inline", "footnote", "hyperlink", "iso", "internal"
]

def call_gemini(prompt: str) -> str:
    """Call Gemini via the official google-genai client."""
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
    except Exception as exc:
        return f"[Gemini error] {exc}"

    text = getattr(response, "text", None)
    if not text:
        return "[Gemini error] Empty response payload."
    return text

def context_aware_rewrite(text: str) -> str:
    prompt = (
        "Rewrite the following text in a professional, precise style while "
        "preserving all technical meaning. Return only the revised text.\n\n"
        f"{text}"
    )
    return call_gemini(prompt)

def extract_json(text: str) -> Optional[dict]:
    """Best-effort attempt to parse JSON returned by the model."""
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        # Handle fenced code blocks by scanning for the first JSON-looking fence payload.
        parts = candidate.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                candidate = part
                break
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def cross_section_consistency_check(document_text: str, focus_section: str = "") -> dict:
    prompt = (
        "You are a compliance editor. Compare the author's work against the company "
        "requirements provided below. Identify every inconsistency in beliefs, tone, "
        "terminology, data values, or formatting. For the focus section, produce a full "
        "rewrite that satisfies the requirements while preserving intent.\n\n"
        "Respond in strict JSON with the keys:\n"
        "- rewritten_section: string containing the compliant rewrite for the focus "
        "  section (or the full document if no focus is supplied)\n"
        "- issues: array of strings, each describing a specific problem found in the "
        "  current document and how to fix it\n"
        "Do not include any additional keys or commentary.\n\n"
    )
    if focus_section:
        prompt += f"Focus section:\n{focus_section}\n\n"

    prompt += (
        f"Company requirements (Markdown):\n{REQUIREMENTS_TEXT}\n\n"
        f"Author document:\n{document_text}"
    )

    raw_response = call_gemini(prompt)
    parsed = extract_json(raw_response)

    if not parsed:
        # Fall back to returning the original content and treat the model response as an issue.
        fallback_text = focus_section or document_text
        return {
            "rewritten_section": fallback_text,
            "issues": [raw_response] if raw_response else ["Consistency check failed without explanation."],
        }

    issues = parsed.get("issues") or []
    if isinstance(issues, str):
        issues = [issues]
    elif not isinstance(issues, list):
        issues = [json.dumps(issues)]

    rewritten = parsed.get("rewritten_section") or (focus_section or document_text)

    return {
        "rewritten_section": rewritten,
        "issues": [issue for issue in issues if isinstance(issue, str) and issue.strip()],
    }

def requirements_alignment_check(document_markdown: str) -> str:
    prompt = (
        "You are a compliance auditor. Compare the provided document against the "
        "company requirements. Identify:\n"
        "- areas that satisfy requirements and cite the matching clauses\n"
        "- gaps or contradictions versus the requirements\n"
        "- terminology/value mismatches that would break compliance\n"
        "- concrete edits needed for alignment\n\n"
        "Conclude with `Overall verdict: PASS` or `Overall verdict: FAIL`.\n\n"
        f"Company requirements (Markdown):\n{REQUIREMENTS_TEXT}\n\n"
        f"Candidate document (Markdown):\n{document_markdown}"
    )
    return call_gemini(prompt)

def docx_to_markdown(file_storage) -> str:
    """Convert an uploaded DOCX (werkzeug FileStorage) into a markdown-like string."""
    try:
        file_bytes = BytesIO(file_storage.read())
        document = Document(file_bytes)
    except Exception as exc:
        raise ValueError(f"Unable to read DOCX file: {exc}") from exc
    finally:
        file_storage.stream.seek(0)

    blocks = []
    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            blocks.append(text)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    if not blocks:
        return ""
    return "\n\n".join(blocks)

@app.route("/")
def home():
    return render_template("index.html", citation_styles=CITATION_STYLES)

@app.route("/process", methods=["POST"])
def process():
    try:
        data = request.json or {}
        text = data.get("text", "")
        action = data.get("action")
        selected_text = data.get("selectedText", "")
        style = data.get("style", "apa")

        if not text and not selected_text:
            return jsonify({"error": "No text provided"}), 400

        segment = selected_text if selected_text else text

        if action == "expand":
            abbr = load_abbreviations()
            expanded, unknown = expand_acronyms(segment, abbr)
            result_text = text.replace(selected_text, expanded) if selected_text else expanded
            return jsonify({"result": result_text, "unknown_acronyms": unknown})

        if action == "citation":
            if style not in CITATION_STYLES:
                style = "apa"
            detected = detect_citation_style(segment)
            formatted = format_citation(style, segment)
            result_text = text.replace(selected_text, formatted) if selected_text else formatted
            return jsonify({"result": result_text, "detected_style": detected})

        if action == "rewrite":
            rewritten = context_aware_rewrite(segment)
            result_text = text.replace(selected_text, rewritten) if selected_text else rewritten
            return jsonify({"result": result_text})

        if action == "consistency":
            review = cross_section_consistency_check(text or segment, selected_text)
            rewritten = review.get("rewritten_section", segment)
            issues = review.get("issues", [])

            if selected_text:
                updated_document = text.replace(selected_text, rewritten, 1)
            else:
                updated_document = rewritten

            if issues:
                issues_report = "Problems detected:\n" + "\n".join(f"- {item}" for item in issues)
            else:
                issues_report = "No problems detected; the document aligns with company requirements."

            return jsonify({
                "result": issues_report,
                "issues": issues,
                "rewrite": rewritten,
                "updated_document": updated_document
            })

        if action == "requirements_consistency":
            analysis = requirements_alignment_check(segment)
            return jsonify({"result": analysis})

        return jsonify({"error": "Unknown action"}), 400

    except Exception as e:
        return jsonify({"error": f"Server error: {e}"}), 500

@app.route("/upload", methods=["POST"])
def upload_document():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part in the request"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        if not file.filename.lower().endswith(".docx"):
            return jsonify({"error": "Unsupported file type. Upload a .docx document."}), 400

        markdown_text = docx_to_markdown(file)
        if not markdown_text:
            return jsonify({"error": "Uploaded document is empty or could not be parsed"}), 400

        analysis = requirements_alignment_check(markdown_text)
        return jsonify({"result": analysis, "markdown": markdown_text})

    except Exception as exc:
        return jsonify({"error": f"Upload processing failed: {exc}"}), 500

if __name__ == "__main__":
    print("BizRefine Flask (Gemini) on http://127.0.0.1:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
