import requests
import json
import time
import os
# from transformers import AutoTokenizer, AutoModelForSeq2SeqLM # <-- T5 Model REMOVED

# -----------------------------------------------------------------
# T5 Model REMOVED
# We will use the Gemini API for all rewrites as it's more powerful
# and avoids the "True" bug.
# -----------------------------------------------------------------

# -----------------------------------------------------------------
# Gemini API call (for fixing conflicts AND rewrites)
# -----------------------------------------------------------------
def call_gemini_api(system_prompt: str, user_prompt: str, response_schema=None) -> str:
    """
    Calls the Gemini API with a specific system and user prompt.
    Returns the generated text. Can be configured to return JSON.
    """
    apiKey = os.getenv("GEMINI_API_KEY")
    if not apiKey:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        return "Error: API key not configured on server. Please set GEMINI_API_KEY in .env file."

    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={apiKey}"
    
    payload = {
        "contents": [{ "parts": [{ "text": user_prompt }] }],
        "systemInstruction": {
            "parts": [{ "text": system_prompt }]
        }
    }
    
    # [NEW] Add JSON schema if one is provided
    if response_schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }

    max_retries = 3
    delay = 1
    for attempt in range(max_retries):
        try:
            response = requests.post(apiUrl, json=payload, headers={'Content-Type': 'application/json'})
            
            if response.status_code == 200:
                result = response.json()
                text_part = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                return text_part.strip()
            else:
                print(f"API Error: Status {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return "Error: Unable to generate rewrite."
    return "Error: All retry attempts failed."

# -----------------------------------------------------------------
# [MODIFIED] 'Rewrite Section' now uses Gemini for 3 options
# -----------------------------------------------------------------
def rewrite_section(text: str) -> dict:
    """
    Generates 3 rewrite options (Professional, Concise, Simpler)
    for the 'Rewrite Section' button using the Gemini API.
    Returns a JSON string, which Flask will pass to the frontend.
    """
    print("Calling Gemini API for 3 rewrite options...")
    
    system_prompt = (
        "You are an expert editor. The user will provide text. "
        "You must generate three distinct rewrites: "
        "1. professional: Formal, corporate, and polished. "
        "2. concise: As short as possible while keeping the core meaning. "
        "3. simpler: Easy to understand, avoids jargon. "
        "You must respond *only* with a JSON object."
    )
    
    user_prompt = f"Original text to rewrite:\n\n\"{text}\""
    
    # Define the JSON schema we want the model to return
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "original": { "type": "STRING" },
            "professional": { "type": "STRING" },
            "concise": { "type": "STRING" },
            "simpler": { "type": "STRING" }
        },
        "propertyOrdering": ["original", "professional", "concise", "simpler"]
    }
    
    # The API will return a JSON *string* that matches this schema
    # We add the original text to the prompt so the model can include it in its JSON response
    json_response_string = call_gemini_api(
        system_prompt, 
        f"{user_prompt}\n\nReturn JSON with 'original' set to the original text.", 
        json_schema
    )
    
    # Convert the JSON string into a Python dict to send to the frontend
    try:
        # We parse the JSON string here, so app.py gets a dictionary
        loaded_json = json.loads(json_response_string)
        # Ensure 'original' key is present
        if 'original' not in loaded_json:
             loaded_json['original'] = text
        return loaded_json
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from model: {json_response_string}")
        return {
            "original": text,
            "professional": "Error: Could not generate rewrite.",
            "concise": "Error: Could not generate rewrite.",
            "simpler": "Error: Could not generate rewrite."
        }


# -----------------------------------------------------------------
# 'Fix Conflicts' (still uses Gemini API)
# -----------------------------------------------------------------
def rewrite_to_fix_conflicts(original_text: str, issues_report: str) -> str:
    """
    Advanced rewrite to fix detected inconsistencies.
    This still uses the Gemini API as it's the only one that
    can reliably follow the instruction to "fix these specific errors."
    """
    print("Calling Gemini to fix detected inconsistencies...")
    
    system_prompt = (
        "You are an expert document editor. Your task is to rewrite a piece of text to resolve a specific list of "
        "detected contradictions. You must produce a single, clean, and professionally written block of text "
        "that is logically consistent. Do not just comment on the errors; fix them."
    )
    
    user_prompt = (
        f"Please rewrite the following text to resolve all the inconsistencies listed below.\n\n"
        f"--- ORIGINAL TEXT ---\n"
        f"\"{original_text}\"\n\n"
        f"--- DETECTED INCONSISTENCIES ---\n"
        f"\"{issues_report}\"\n\n"
        f"--- CORRECTED, PROFESSIONAL VERSION ---\n"
    )
    
    # This call does not need a JSON schema
    corrected_text = call_gemini_api(system_prompt, user_prompt)
    return corrected_text