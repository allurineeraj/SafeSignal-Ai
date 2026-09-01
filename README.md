# SIF-Insight

SIF-Insight is a localized, privacy-first decision-support prototype for identifying Serious Injury or Fatality (SIF) precursors from safety reports.

## Features
- **Worker Report Submission**: Workers can submit safety reports (Unsafe Acts, Conditions, Near Misses) with attachments (PDF, DOCX, XLSX, TXT, images). Text extraction works natively for documents.
- **AI-Assisted Classification**: 3-layer hybrid SIF classifier using rule-based NLP for Life-Saving Rules extraction, heuristic scoring, and a fallback to TF-IDF `LogisticRegression` ML model.
- **Similar Report Detection**: Uses TF-IDF and Cosine Similarity to detect duplicated narratives on submission, and provides an AI-powered "Similar Reports" explorer view to identify recurring hazards.
- **HSE Review Queue**: Status transitions from *Submitted* to *Pending HSE Review*, *Action Assigned*, and *Closed*. Includes complete corrective action tracking.
- **Analytics Dashboard**: Dynamic heatmaps, Pareto charts of failed barriers, and KPI aggregation computed directly from the SQLite database.
- **Taxonomy Integration**: Embedded IOGP Life-Saving Rules keywords mapped directly to report text to highlight specific barrier failures.

## Architecture & Fallback Mechanisms
This system is designed to run in highly restricted networks where cloud access is prohibited:
- **Speech-to-Text**: Defaults to demo/manual fallback if local models are unavailable.
- **Translation**: Defaults to fallback if heavy translation models (IndicTrans2) are missing.
- **Embeddings/Similarity**: Gracefully degrades from `sentence-transformers` to standard TF-IDF `scikit-learn` Cosine Similarity.
- **Text Extraction**: Uses `pymupdf` (fitz) and `python-docx` for native parsing; degrades gracefully for OCR images.

## Installation
1. Clone the repository and initialize a virtual environment (`python -m venv .venv`).
2. Activate the virtual environment (`.venv\Scripts\activate` on Windows, or `source .venv/bin/activate` on UNIX).
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Optional: If you want to use heavy models, install the optional requirements:
   ```bash
   pip install -r requirements-optional-models.txt
   ```

## Getting Started
1. Run the database seed and ML training script to generate 80+ records and train the classifier:
   ```bash
   python scripts/create_demo_data.py
   ```
2. Start the Streamlit application:
   ```bash
   streamlit run app.py
   ```
3. Use the sidebar to toggle between Worker, HSE Officer, and Admin roles.
