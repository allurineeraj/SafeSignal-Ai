import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db.sqlite")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    columns_to_add_ai = [
        ("actual_injury", "TEXT"),
        ("explanation", "TEXT"),
        ("llm_provider", "TEXT"),
        ("llm_model", "TEXT"),
        ("llm_analysis_status", "TEXT"),
        ("llm_confidence", "REAL"),
    ]
    
    columns_to_add_hse = [
        ("final_actual_injury", "TEXT")
    ]

    print("Migrating ai_predictions table...")
    for col_name, col_type in columns_to_add_ai:
        try:
            cursor.execute(f"ALTER TABLE ai_predictions ADD COLUMN {col_name} {col_type}")
            print(f"Added {col_name} to ai_predictions")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {col_name} already exists in ai_predictions")
            else:
                print(f"Error adding {col_name}: {e}")

    print("Migrating hse_reviews table...")
    for col_name, col_type in columns_to_add_hse:
        try:
            cursor.execute(f"ALTER TABLE hse_reviews ADD COLUMN {col_name} {col_type}")
            print(f"Added {col_name} to hse_reviews")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {col_name} already exists in hse_reviews")
            else:
                print(f"Error adding {col_name}: {e}")

    # Also migrate test database if it exists
    test_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_db.sqlite")
    if os.path.exists(test_db_path):
        print("\nMigrating test_db.sqlite...")
        test_conn = sqlite3.connect(test_db_path)
        test_cursor = test_conn.cursor()
        
        for col_name, col_type in columns_to_add_ai:
            try:
                test_cursor.execute(f"ALTER TABLE ai_predictions ADD COLUMN {col_name} {col_type}")
                print(f"Added {col_name} to test_db.sqlite ai_predictions")
            except Exception:
                pass
                
        for col_name, col_type in columns_to_add_hse:
            try:
                test_cursor.execute(f"ALTER TABLE hse_reviews ADD COLUMN {col_name} {col_type}")
                print(f"Added {col_name} to test_db.sqlite hse_reviews")
            except Exception:
                pass
                
        test_conn.commit()
        test_conn.close()

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
