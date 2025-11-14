# app.py
# -----------------------------------------------------
# BizRefine NLP Backend Server (FIXED)
# -----------------------------------------------------
# Modules:
#   • Acronym Expansion (Model-Based)
#   • Citation Formatter
#   • Context-Aware Rewriting (Simple)
#   • Consistency Check (with AI-Powered Fixes)
# -----------------------------------------------------

import os
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from docx import Document
from dotenv import load_dotenv 
# ---- Import local modules ----
# We use "acroynom.py" to match the file I am providing
from acroynom import load_abbreviations, expand_acronyms
# from citations import detect_citation_style, format_citation
from rewrite_model import rewrite_section, rewrite_to_fix_conflicts
from consistency_model import analyze_cross_section

# ---- Load Environment Variables ----
load_dotenv() 
# This will load the GEMINI_API_KEY from your .env file
# -----------------------------------------------------
# Flask Setup
# -----------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# -----------------------------------------------------
# DOCX to text helper
# -----------------------------------------------------
def docx_to_text(file_storage) -> str:
    """Converts a .docx file (from upload) into plain text."""
    try:
        file_bytes = BytesIO(file_storage.read())
        document = Document(file_bytes)
    finally:
        # Reset stream position for any future reads
        file_storage.stream.seek(0)
    return "\n\n".join(p.text.strip() for p in document.paragraphs if p.text.strip())

# -----------------------------------------------------
# Routes
# -----------------------------------------------------
@app.route("/")
def index():
    # Serves the main HTML user interface
    return send_from_directory("static", "taskpane.html")

@app.route("/process", methods=["POST"])
def process():
    """Main API endpoint to handle all NLP actions."""
    try:
        data = request.json or {}
        action = data.get("action")
        text = data.get("text", "")
        style = data.get("style", "apa") # For citation formatting

        if not text:
            return jsonify({"error": "No text provided"}), 400

        # ---------- Acronym Expansion ----------
        if action == "expand":
            # [FIX] This function only takes one argument
            expanded, unknown = expand_acronyms(text)
            return jsonify({"result": expanded, "unknown": unknown})

        # ---------- Citation Formatter ----------
        elif action == "citation":
            # Placeholder: Implement detect_citation_style and format_citation in citations.py
            # detected = detect_citation_style(text)
            # formatted = format_citation(style, text)
            # return jsonify({"result": formatted, "detected": detected})
            print("Citation action called, but 'citations.py' is not implemented.")
            return jsonify({"result": text, "detected": "N/A (Not Implemented)"})

        # ---------- Context-Aware Rewrite ----------
        elif action == "rewrite":
            # Calls the simple rewrite function
            output = rewrite_section(text)
            return jsonify(output)

        # ---------- Cross-Section Consistency ----------
        elif action == "consistency":
            # This is the new, advanced workflow
            
            # 1. Get the analysis from the local consistency model
            analysis = analyze_cross_section(text)
            
            suggested_rewrite = None
            
            # 2. Check if the report found any problems
            if "Inconsistencies detected" in analysis.get("issues_report", ""):
                # 3. If so, call the Gemini API to suggest a fix
                print("Inconsistencies found. Calling rewrite model...")
                suggested_rewrite = rewrite_to_fix_conflicts(
                    text, 
                    analysis["issues_report"]
                )
            
            # 4. Return both the analysis AND the suggestion
            # The 'analysis' dict already contains 'consistency_results' and 'issues_report'
            return jsonify({
                **analysis,
                "suggested_rewrite": suggested_rewrite
            })

        else:
            return jsonify({"error": f"Unknown action '{action}'"}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/upload", methods=["POST"])
def upload():
    """Handles .docx file uploads and converts them to text."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.docx'):
        text = docx_to_text(file)
        return jsonify({"text": text})
    else:
        return jsonify({"error": "Invalid file type. Please upload a .docx file."}), 400

# -----------------------------------------------------
# Run
# -----------------------------------------------------
if __name__ == "__main__":
    # [FIX] Use app.run() which is the standard Flask (WSGI) server.
    # This replaces the Uvicorn (ASGI) server that was causing the TypeError.
    
    # Check for 'requests' library, as it's vital for API calls
    try:
        import requests
    except ImportError:
        print("-------------------------------------------------------")
        print("ERROR: 'requests' library not found.")
        print("Please install it to use the model-based features:")
        print("pip install requests")
        print("-------------------------------------------------------")
        
    app.run(host="127.0.0.1", port=5001, debug=True)