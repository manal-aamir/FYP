import json
import re
import os


ABBREVIATION_FILE = "abbreviations_local.json"
INPUT_FILE = "acronym_test.txt"
OUTPUT_FILE = "acronym_test_extended_expanded.txt"

def load_abbreviations(file_path=ABBREVIATION_FILE) -> dict:
    """Loads the abbreviation JSON or creates an empty one if not found."""
    if not os.path.exists(file_path):
        print(f" No abbreviation file found, creating new one: {file_path}")
        with open(file_path, "w") as f:
            json.dump({}, f)
        return {}
    with open(file_path, "r") as f:
        return json.load(f)

ABBREVIATIONS = load_abbreviations()

def expand_acronyms(text: str, abbreviations: dict = ABBREVIATIONS) -> tuple[str, list[str]]:
    """
    Expands acronyms in the given text using the abbreviation dictionary.
    Returns (expanded_text, list_of_unknown_acronyms).
    """
    unknown = set()
    # Detect likely acronyms (2+ uppercase letters)
    words = set(re.findall(r"\b[A-Z]{2,}\b", text))

    for acronym in words:
        key = acronym.lower()
        if key in abbreviations:
            pattern = r"\b" + re.escape(acronym) + r"\b"
            text = re.sub(
                pattern,
                f"{abbreviations[key].title()} ({acronym.upper()})",
                text,
                flags=re.IGNORECASE
            )
        else:
            unknown.add(acronym)

    return text, sorted(list(unknown))

def process_file(input_path: str, output_path: str):
    """Reads text file, expands acronyms, saves expanded version."""
    if not os.path.exists(input_path):
        print(f" File not found: {input_path}")
        return

    with open(input_path, "r") as infile:
        text = infile.read()

    expanded_text, unknown = expand_acronyms(text)

    with open(output_path, "w") as outfile:
        outfile.write(expanded_text)

    print(f" Processed file: {input_path}")
    print(f" Expanded version saved as: {output_path}")

    if unknown:
        print("\n The following acronyms were not found in your JSON file:")
        print(", ".join(unknown))
        print("\n Add them using extend_json('ACRONYM', 'meaning') later.\n")
    else:
        print("\n All acronyms were expanded successfully!\n")

def extend_json(acronym: str, meaning: str, file_path=ABBREVIATION_FILE):
    """Adds a new acronym to the abbreviation JSON file."""
    with open(file_path, "r+") as f:
        data = json.load(f)
        if acronym.lower() not in data:
            data[acronym.lower()] = meaning.lower()
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
            print(f"Added {acronym.upper()} = {meaning}")
        else:
            print(f"ℹ {acronym.upper()} already exists.")

if __name__ == "__main__":
    process_file(INPUT_FILE, OUTPUT_FILE)
