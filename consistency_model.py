# consistency_model.py
# -----------------------------------------
# Cross-Section Consistency Analyzer (FIXED)
# - Compares ALL sentence pairs
# - Smart context checking for numbers
# -----------------------------------------

import re
import nltk
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
from itertools import combinations # <-- Correctly checks all pairs
from nltk.corpus import wordnet
import numpy as np

# Download required NLTK components
nltk.download("punkt", quiet=True)
nltk.download("wordnet", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("punkt_tab", quiet=True) 

# Load lightweight DistilBERT NLI model
MODEL_NAME = "typeform/distilbert-base-uncased-mnli"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
nli_pipeline = pipeline("text-classification", model=model, tokenizer=tokenizer)

# --------------------------
# Global Context Dictionary
# --------------------------
CONTEXTS = {
    "financial": {
        "units": ["$", "USD", "PKR", "€", "£"], 
        "keywords": ["budget", "cost", "price", "total", "expense", "fund", "payment", "revenue", "profit", "loss"],
        "synonyms": set()
    },
    "temporal": {
        "units": ["month", "day", "year", "week", "quarter"],
        "keywords": ["deadline", "timeline", "duration", "schedule", "plan", "milestone"],
        "synonyms": set()
    },
    "performance": {
        "units": ["%", "percent"],
        "keywords": ["KPI", "metric", "performance", "target", "goal", "achievement"],
        "synonyms": set()
    }
}

def get_synonyms(word):
    """Get synonyms for a word using WordNet."""
    synonyms = set()
    for syn in wordnet.synsets(word):
        for lemma in syn.lemmas():
            synonyms.add(lemma.name().lower())
    return synonyms

def initialize_contexts():
    """Populates the global CONTEXTS dictionary with synonyms."""
    global CONTEXTS
    for context_data in CONTEXTS.values():
        for keyword in context_data["keywords"]:
            context_data["synonyms"].update(get_synonyms(keyword))

# --------------------------
# Utility functions
# --------------------------

def split_into_sentences(text: str):
    """Tokenize text into clean, unique sentences with context."""
    sentences = nltk.sent_tokenize(text)
    return [s.strip() for s in sentences if s.strip()]

def convert_to_number(text):
    """Convert written numbers and numeric strings to float values."""
    number_words = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'hundred': 100, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000
    }
    
    text = text.lower().strip()
    if text in number_words:
        return float(number_words[text])
    try:
        text = text.replace('$', '').replace('€', '').replace('£', '').replace(',', '')
        if '%' in text:
            return float(text.replace('%', '')) / 100
        return float(text)
    except ValueError:
        return None

def detect_numeric_mismatch(sent1: str, sent2: str) -> dict:
    """Enhanced numeric inconsistency detection with context awareness."""
    patterns = [
        r"(\d+(?:,\d{3})*(?:\.\d+)?)",  # Regular numbers with commas
        r"(\d+(?:\.\d+)?%)",             # Percentages
        r"(\$\d+(?:,\d{3})*(?:\.\d+)?)", # Dollar amounts
        r"(€\d+(?:,\d{3})*(?:\.\d+)?)",  # Euro amounts
        r"(£\d+(?:,\d{3})*(?:\.\d+)?)",  # Pound amounts
    ]
    
    nums1, nums2 = [], []
    for pattern in patterns:
        nums1.extend(re.findall(pattern, sent1, re.IGNORECASE))
        nums2.extend(re.findall(pattern, sent2, re.IGNORECASE))
    
    nums1_conv = [str(convert_to_number(n)) for n in nums1 if convert_to_number(n) is not None]
    nums2_conv = [str(convert_to_number(n)) for n in nums2 if convert_to_number(n) is not None]
    
    if not nums1_conv or not nums2_conv:
        return {"mismatch": False, "reason": "No numbers to compare"}
    
    for context_name, context_data in CONTEXTS.items():
        all_terms = context_data["units"] + context_data["keywords"] + list(context_data["synonyms"])
        sent1_has_context = any(term.lower() in sent1.lower() for term in all_terms)
        sent2_has_context = any(term.lower() in sent2.lower() for term in all_terms)
        
        if sent1_has_context and sent2_has_context and set(nums1_conv) != set(nums2_conv):
            return {
                "mismatch": True,
                "reason": f"Numeric mismatch in {context_name} context: {set(nums1_conv)} vs {set(nums2_conv)}"
            }

    return {"mismatch": False, "reason": "No contextual numeric mismatch detected"}

def check_consistency(sentence1: str, sentence2: str) -> dict:
    """Enhanced consistency checker."""
    try:
        numeric_result = detect_numeric_mismatch(sentence1, sentence2)
        combined_input = f"{sentence1} </s> {sentence2}"
        nli_result = nli_pipeline(combined_input)[0]
        label = nli_result["label"]
        score = round(nli_result["score"], 3)
        
        response = {
            "sentence1": sentence1,
            "sentence2": sentence2,
            "confidence": score,
            "numeric_analysis": numeric_result
        }
        
        if numeric_result["mismatch"]:
            response.update({
                "verdict": "❌ Numeric Mismatch",
                "label": "CONTRADICTION",
                "suggestion": f"Inconsistency detected: {numeric_result['reason']}"
            })
        elif label == "CONTRADICTION":
            response.update({
                "verdict": "❌ Logical Contradiction",
                "label": "CONTRADICTION",
                "suggestion": "These statements express conflicting information."
            })
        elif label == "ENTAILMENT":
            response.update({
                "verdict": "✅ Consistent",
                "label": "ENTAILMENT",
                "suggestion": "Statements are logically and numerically consistent."
            })
        else:
            response.update({
                "verdict": "⚪ Neutral",
                "label": "NEUTRAL",
                "suggestion": "No clear logical relation or numeric inconsistency detected."
            })
        
        return response
            
    except Exception as e:
        return {
            "sentence1": sentence1,
            "sentence2": sentence2,
            "verdict": f"⚠️ Error: {e}",
            "label": "ERROR",
            "confidence": 0.0,
            "suggestion": "Check input formatting or model initialization.",
            "numeric_analysis": {"mismatch": False, "reason": "Error in analysis"}
        }

def analyze_cross_section(document_text: str):
    """Analyzes all pairs of sentences for inconsistencies."""
    sentences = split_into_sentences(document_text)
    
    if len(sentences) < 2:
        return {"consistency_results": [], "issues_report": "ℹ️ Not enough text to check."}
        
    results, contradictions = [], []
    
    # [FIX] Use combinations to check ALL pairs
    for sent1, sent2 in combinations(sentences, 2):
        result = check_consistency(sent1, sent2)
        results.append(result)
        if (result["label"] == "CONTRADICTION" or 
            (result.get("numeric_analysis", {}).get("mismatch", False))):
            contradictions.append(result)

    if contradictions:
        summary_lines = ["⚠️ Inconsistencies detected:"]
        numeric_issues = [c for c in contradictions if c.get("numeric_analysis", {}).get("mismatch", False)]
        logical_issues = [c for c in contradictions if c["label"] == "CONTRADICTION" and 
                                    not c.get("numeric_analysis", {}).get("mismatch", False)]
        
        if numeric_issues:
            summary_lines.append("\n🔢 Numeric Inconsistencies:")
            for issue in numeric_issues:
                line = f"- {issue['numeric_analysis']['reason']}\n  \"{issue['sentence1']}\" vs.\n  \"{issue['sentence2']}\""
                summary_lines.append(line)
        
        if logical_issues:
            summary_lines.append("\n❌ Logical Contradictions:")
            for issue in logical_issues:
                line = f"- {issue['suggestion']}\n  \"{issue['sentence1']}\" vs.\n  \"{issue['sentence2']}\""
                summary_lines.append(line)
                
        summary = "\n".join(summary_lines)
    else:
        summary = "✅ No inconsistencies detected; the document aligns logically."

    return {
        "consistency_results": results,
        "issues_report": summary,
    }

initialize_contexts()