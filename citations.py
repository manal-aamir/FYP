import re

def detect_citation_style(text: str) -> str:
    """Roughly detect the citation style by pattern."""
    t = text.strip()

    # Academic styles
    if re.search(r"\(\d{4}\)", t) and re.search(r"\.", t.split(")")[0]):
        return "apa"
    if re.search(r"\[\d+\]", t):
        return "ieee"
    if re.match(r"^\d+\.", t):
        return "vancouver"
    if "et al." in t and '"' in t:
        return "mla"
    if re.search(r"\(\d{4}\)", t) and t.count(",") >= 2:
        return "harvard"
    if re.search(r"\d{4}\)$", t) and '"' in t:
        return "chicago"

    # Business / corporate styles
    if t.lower().startswith("according to"):
        return "inline"
    if re.search(r"¹|²|³", t):
        return "footnote"
    if re.search(r"https?://", t):
        return "hyperlink"
    if re.search(r"iso|iec|ieee", t.lower()):
        return "iso"
    if re.search(r"ref\.", t.lower()):
        return "internal"

    return "unknown"


def format_citation(style: str, text: str) -> str:
    """Convert text into chosen style (mock transformation)."""
    style = style.lower()
    base_info = extract_core_info(text)

    if style == "apa":
        return f"{base_info['author']} ({base_info['year']}). {base_info['title']}. {base_info['source']}."
    if style == "ieee":
        return f"{base_info['author']}, \"{base_info['title']},\" {base_info['source']}, {base_info['year']}."
    if style == "mla":
        return f"{base_info['author']}. \"{base_info['title']}.\" {base_info['source']}, {base_info['year']}."
    if style == "chicago":
        return f"{base_info['author']}. \"{base_info['title']}.\" {base_info['source']} ({base_info['year']})."
    if style == "harvard":
        return f"{base_info['author']} ({base_info['year']}) {base_info['title']}. {base_info['source']}."
    if style == "inline":
        return f"According to {base_info['author']} ({base_info['year']}), {base_info['title']}."
    if style == "footnote":
        return f"¹ {base_info['author']} ({base_info['year']}), {base_info['title']}, {base_info['source']}."
    if style == "hyperlink":
        return f"{base_info['title']} — [Source]({base_info['url']}) ({base_info['year']})"
    if style == "iso":
        return f"ISO/IEC {base_info['source']}: {base_info['title']} ({base_info['year']})."
    if style == "internal":
        return f"Ref. No. {base_info['source']} — {base_info['title']} ({base_info['year']})"
    return text

def extract_core_info(text: str):
    """Extract key components for cross-format conversion."""
    author_match = re.search(r"According to ([A-Za-z& ]+)", text)
    author = author_match.group(1).strip() if author_match else re.split(r"[,.\(]", text)[0].strip()
    year_match = re.search(r"\(?(\d{4})\)?", text)
    year = year_match.group(1) if year_match else "n.d."
    title_match = re.search(r"[,\"“”']\s*([^\"“”']+)[\"“”']", text)
    title = title_match.group(1) if title_match else "Untitled"
    source_match = re.search(r"\b([A-Z][A-Za-z0-9&\- ]+)\b", text.split(year)[-1]) if year in text else None
    source = source_match.group(1).strip() if source_match else "Unknown Source"
    url_match = re.search(r"(https?://[^\s]+)", text)
    url = url_match.group(1) if url_match else "https://example.com"
    return {"author": author, "year": year, "title": title, "source": source, "url": url}

if __name__ == "__main__":
    print("📚 Universal Citation Converter (Academic + Business)\n")
    user_input = input("Enter your citation: ").strip()

    detected = detect_citation_style(user_input)
    print(f"\n🔍 Detected Style: {detected.upper() if detected != 'unknown' else 'Could not detect'}")

    print("\nAvailable target styles:")
    styles = [
        "APA", "MLA", "IEEE", "CHICAGO", "HARVARD",
        "INLINE", "FOOTNOTE", "HYPERLINK", "ISO", "INTERNAL"
    ]
    for i, s in enumerate(styles, start=1):
        print(f"{i}. {s}")

    choice = int(input("\nSelect target style (number): "))
    target_style = styles[choice - 1].lower()

    converted = format_citation(target_style, user_input)
    print(f"\n Converted to {target_style.upper()}:\n{converted}")
