import json
import re
import os       # <-- IMPORT OS
import requests
import time

ABBREVIATION_FILE = "abbreviations_local.json"

def load_abbreviations(file_path=ABBREVIATION_FILE) -> dict:
    # ... (rest of function is unchanged)
    if not os.path.exists(file_path):
        print(f" No abbreviation file found, creating new one: {file_path}")
        with open(file_path, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: Corrupt JSON file at {file_path}. Creating a new one.")
        with open(file_path, "w") as f:
            json.dump({}, f)
        return {}

def save_abbreviations(data: dict, file_path=ABBREVIATION_FILE):
    # ... (rest of function is unchanged)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def get_expansions_from_model(acronyms: list, full_text: str) -> dict:
    # ... (rest of function is unchanged)
    print(f"Calling Gemini API to find meanings for: {acronyms}")
    
    system_prompt = (
        "You are an expert-level 'Acronym Disambiguation' tool. "
        "Your job is to determine the full expansion of an acronym based on its context. "
        "Analyze the user's text to find the most likely meaning for each acronym provided. "
        "Respond *only* with a JSON object."
    )
    user_prompt = (
        f"Based on the following document context, what do these acronyms most likely stand for?\n"
        f"Acronyms to find: {', '.join(acronyms)}\n\n"
        f"Document Context:\n\"\"\"\n{full_text}\n\"\"\""
    )
    json_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "acronym": { "type": "STRING" },
                "expansion": { "type": "STRING" }
            },
            "propertyOrdering": ["acronym", "expansion"]
        }
    }
    payload = {
        "contents": [{ "parts": [{ "text": user_prompt }] }],
        "systemInstruction": {
            "parts": [{ "text": system_prompt }]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": json_schema
        }
    }
    
    # [FIX] Read the key from an environment variable
    apiKey = os.getenv("GEMINI_API_KEY")
    if not apiKey:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        return {} # Fail fast if key is missing

    apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={apiKey}"
    
    # ... (rest of function is unchanged)
    max_retries = 3
    delay = 1
    for attempt in range(max_retries):
        try:
            response = requests.post(apiUrl, json=payload, headers={'Content-Type': 'application/json'})
            
            if response.status_code == 200:
                result = response.json()
                text_part = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '{}')
                model_expansions = json.loads(text_part) 
                expansion_dict = {}
                for item in model_expansions:
                    if item.get("acronym") and item.get("expansion"):
                        expansion_dict[item["acronym"].lower()] = item["expansion"].lower()
                return expansion_dict
            else:
                print(f"API Error: Status {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return {}
    return {}

def expand_acronyms(text: str) -> tuple[str, list[str]]:
    # ... (rest of function is unchanged)
    abbreviations = load_abbreviations()
    all_acronyms_in_text = set(re.findall(r"\b[A-Z]{2,}\b", text))
    unknown_acronyms = [ac for ac in all_acronyms_in_text if ac.lower() not in abbreviations]
    
    if unknown_acronyms:
        model_expansions = get_expansions_from_model(unknown_acronyms, text)
        if model_expansions:
            print(f"Model found new expansions: {model_expansions}")
            abbreviations.update(model_expansions)
            save_abbreviations(abbreviations)
        else:
            print("Model could not find expansions for unknown acronyms.")

    expanded_text = text
    final_unknown = []
    
    for acronym in all_acronyms_in_text:
        key = acronym.lower()
        if key in abbreviations:
            pattern = r"\b" + re.escape(acronym) + r"\b"
            expansion_text = f"{abbreviations[key].title()} ({acronym.upper()})"
            expanded_text = re.sub(pattern, expansion_text, expanded_text)
        else:
            final_unknown.append(acronym)

    return expanded_text, sorted(final_unknown)

if __name__ == "__main__":
    def test_run():
        save_abbreviations({"kpi": "key performance indicator"})
        test_text = (
            "The CEO reviewed the project's KPI. "
            "The dev team will use NLP to analyze the data. "
            "This is a test of the ML model."
        )
        print("--- Running Model-Based Acronym Expansion ---")
        expanded, unknown = expand_acronyms(test_text)
        print("\n--- [Original Text] ---")
        print(test_text)
        print("\n--- [Expanded Text] ---")
        print(expanded)
        print("\n--- [Still Unknown] ---")
        print(unknown)
        print("\n--- [Final Dictionary File] ---")
        print(json.dumps(load_abbreviations(), indent=2))
    test_run()