import streamlit as st
import google.generativeai as genai
import json
import re

def validate_row_with_gemini(row_idx, row_series, descriptions, api_key):
    """
    Send the entire row to Gemini and get a dict of column->bool.
    Caches result in session_state.row_validation_cache[row_idx].
    Returns dict {col: bool} or None on error.
    """
    cache = st.session_state.row_validation_cache
    if row_idx in cache:
        return cache[row_idx]

    if not api_key:
        st.warning("Gemini API key not set. Validation skipped.")
        return None

    # Build prompt
    prompt_lines = []
    prompt_lines.append("You are a strict validator. Given a set of columns with descriptions and their corresponding values, decide for each column whether the value satisfies its description.")
    prompt_lines.append("")
    prompt_lines.append("Columns and descriptions:")
    for col, desc in descriptions.items():
        prompt_lines.append(f"- {col}: {desc}")
    prompt_lines.append("")
    prompt_lines.append("Row values:")
    for col in descriptions.keys():
        val = row_series.get(col, "")
        prompt_lines.append(f"- {col}: {val}")
    prompt_lines.append("")
    prompt_lines.append("Return a JSON object mapping each column name to true or false (boolean). Only output valid JSON, no extra text.")
    prompt = "\n".join(prompt_lines)

    try:
        # Configure genai with the provided key (in case it's not already configured)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")  # or gemini-1.5-flash
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Extract JSON (Gemini may wrap in ```json ... ```)
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find a JSON object
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                text = text[start:end]

        result = json.loads(text)
        # Ensure booleans
        validated = {}
        for col in descriptions.keys():
            if col in result:
                validated[col] = bool(result[col])
            else:
                validated[col] = False
        cache[row_idx] = validated
        return validated
    except Exception as e:
        st.error(f"Gemini validation error for row {row_idx+1}: {e}")
        return None