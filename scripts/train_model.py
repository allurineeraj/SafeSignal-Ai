import os
import sqlite3
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db.sqlite")
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "sif_classifier.pkl")

def train_supporting_model():
    """Reads seeded observations from sqlite, trains TF-IDF + LogisticRegression, and saves model."""
    print("--------------------------------------------------")
    print("TRAINING SUPPORTING MACHINE LEARNING MODEL")
    print("--------------------------------------------------")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database file {DB_PATH} not found. Run scripts/create_demo_data.py first.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query texts and their labels from seeded predictions
    cursor.execute("""
        SELECT r.original_text, p.sif_label 
        FROM reports r
        JOIN ai_predictions p ON r.id = p.report_id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("❌ Error: No training records found in database.")
        return
        
    texts = [r['original_text'] for r in rows]
    labels = [r['sif_label'] for r in rows]
    
    print(f"Loaded {len(texts)} training records from database.")
    
    # Fit Pipeline
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=1, lowercase=True)),
        ('clf', LogisticRegression(class_weight='balanced', max_iter=200, random_state=42))
    ])
    
    pipeline.fit(texts, labels)
    print("Successfully fit TF-IDF + Logistic Regression pipeline.")
    
    # Save Model
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)
        
    print(f"Model saved successfully to {MODEL_PATH}")
    print("--------------------------------------------------\n")

if __name__ == "__main__":
    train_supporting_model()
