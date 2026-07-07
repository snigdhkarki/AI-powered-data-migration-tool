# CSV Row Migration Tool with AI Validation

A Streamlit‑based application that helps you migrate rows from a source CSV to a destination CSV, with per‑cell validation powered by **Google Gemini AI**. You can review each row, accept, reject, or modify it, and save your progress at any time.

![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)

---

## live app at:
https://ai-powered-data-migration-tool-zq9qjlfre674q9zxpec9rw.streamlit.app/

## live app without AI:
https://migrationtoolsnigdh.streamlit.app/

## Features

- **Interactive row‑by‑row migration** – Process rows from the source file sequentially.
- **Gemini‑powered validation** – Each cell is validated against a user‑defined description (e.g., "must be a valid email").
- **Visual feedback** – Valid cells are highlighted green, invalid ones red.
- **Accept / Reject / Modify** – Accept a row as‑is, reject it, or edit it before saving.
- **Checkpoint & resume** – Download the remaining source rows and the destination CSV to resume later.
- **Editable destination table** – Click any cell in the destination grid to update it manually.
- **Undo last action** – Revert the last accept/reject operation.
- **Persistent cache** – Validation results are cached to avoid repeated API calls.

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/csv-migrator-ai.git
   cd csv-migrator-ai
Create and activate a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies
```
```bash
pip install -r requirements.txt
Get a Gemini API key
```
Visit Google AI Studio and create an API key.

You will enter this key in the app’s sidebar.

Usage
Run the app

```bash
streamlit run main.py
```

Upload your source CSV (required).
Optionally upload a destination CSV to resume a previous migration.

Define column descriptions – For each column, provide a short description that the cell value should satisfy (e.g., must be a positive number). These descriptions are used by Gemini to validate each cell.

Enter your Gemini API key in the sidebar.

Process rows – Each row is displayed with:

Green cells – valid according to Gemini.

Red cells – invalid.

Buttons to Accept, Reject, or Modify the row.

Modify mode – Edit any field, then save the modified row.

Destination table – On the right side, you can click any cell and edit it directly. Press Save Changes to persist.

Progress tracking – The sidebar shows how many rows are processed, accepted, and remaining. Use the Download buttons to create checkpoints.

Undo – Revert the most recent accept/reject action.

## How It Works
The app reads the source CSV and (optionally) a destination CSV with the same column structure.

For each row, it sends the row values along with the column descriptions to Gemini, asking the model to return a JSON mapping each column to true or false based on the description.

The validation result is cached in st.session_state so repeated review of the same row doesn’t trigger new API calls.

Accepted rows are appended to the destination DataFrame, which is displayed in an editable grid.

All state (source, destination, current index, history, validation cache) is preserved across reruns via Streamlit’s session state.


## Configuration
Column descriptions – Entered through the UI; saved in st.session_state.

Gemini model – Currently set to gemini-2.5-flash-lite (change in ai_validator.py if needed).

API key – Input in the sidebar; also stored in session state.

## Dependencies
All required packages are listed in requirements.txt:

streamlit

pandas

numpy

streamlit-aggrid

google-generativeai
