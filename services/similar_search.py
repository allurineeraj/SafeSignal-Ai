import sqlite3
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from database.db import get_connection

def find_similar_reports(current_report_id: int, current_text: str, threshold: float = 0.15) -> list[dict]:
    """Identify similar reports in SQLite database using TF-IDF and Cosine Similarity."""
    conn = get_connection()
    # Fetch all other reports
    query = "SELECT id, report_type, original_text FROM reports WHERE id != ? AND original_text IS NOT NULL"
    df = pd.read_sql_query(query, conn, params=(current_report_id,))
    conn.close()

    if df.empty or not current_text.strip():
        return []

    # Compute TF-IDF
    vectorizer = TfidfVectorizer(stop_words='english')
    texts = [current_text] + df['original_text'].tolist()
    
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        # Happens if vocabulary is empty
        return []

    # Compute cosine similarity between current_text and all others
    cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    # Filter by threshold
    similar_indices = [i for i, score in enumerate(cosine_sim) if score >= threshold]
    
    # Build results
    results = []
    for idx in similar_indices:
        results.append({
            "id": int(df.iloc[idx]["id"]),
            "report_type": df.iloc[idx]["report_type"],
            "original_text": df.iloc[idx]["original_text"],
            "similarity_score": round(float(cosine_sim[idx]), 3)
        })
        
    # Sort by descending similarity
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:5] # Return top 5

def check_for_duplicates(new_text: str, threshold: float = 0.80) -> tuple[bool, list[dict]]:
    """Check duplicate submissions before insertion."""
    conn = get_connection()
    query = "SELECT id, report_type, original_text FROM reports WHERE original_text IS NOT NULL"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty or not new_text.strip():
        return False, []

    vectorizer = TfidfVectorizer(stop_words='english')
    texts = [new_text] + df['original_text'].tolist()
    
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return False, []

    cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    similar_indices = [i for i, score in enumerate(cosine_sim) if score >= threshold]
    
    results = []
    for idx in similar_indices:
        results.append({
            "id": int(df.iloc[idx]["id"]),
            "report_type": df.iloc[idx]["report_type"],
            "original_text": df.iloc[idx]["original_text"],
            "similarity_score": round(float(cosine_sim[idx]), 3)
        })
        
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    
    return len(results) > 0, results[:5]
