import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("--- STARTING END-TO-END TEST ---")
    
    # 1. Test Supabase Schema / Queue
    print("1. Fetching HSE Queue to verify Supabase schema...")
    try:
        res = requests.get(f"{BASE_URL}/api/queue")
        if res.status_code != 200:
            print(f"FAIL: Queue fetch failed: {res.text}")
            return
        print(f"PASS: Queue fetched. Found {len(res.json())} pending reports.")
    except Exception as e:
        print(f"FAIL: Connection error: {e}")
        return

    # 2. Test Login
    print("\n2. Testing HSE001 Authentication...")
    res = requests.post(f"{BASE_URL}/api/login", json={"user_id": "HSE001", "password": "HSE@1234"})
    if res.status_code != 200:
        print(f"FAIL: Login rejected. Is user in Supabase? Response: {res.text}")
        return
    print("PASS: Authentication successful.")
    
    # 3. Test Report Submission (Simulating worker voice result)
    print("\n3. Testing Report Submission...")
    report_data = {
        "original_text": "There is a massive oil spill on the catwalk near generator 4. It is very slippery.",
        "translated_text": "There is a massive oil spill on the catwalk near generator 4. It is very slippery.",
        "language": "English"
    }
    res = requests.post(f"{BASE_URL}/api/submit_report", json=report_data)
    if res.status_code != 200:
        print(f"FAIL: Report submission failed: {res.text}")
        return
    submit_res = res.json()
    report_id = submit_res.get("report_id")
    print(f"PASS: Report submitted successfully to Supabase! ID: {report_id}")
    print(f"      AI Classification: {submit_res.get('sif_label')} - Priority: {submit_res.get('priority')}")
    
    time.sleep(1) # Let db settle
    
    # 4. Verify in Queue
    print("\n4. Verifying Report is in Queue...")
    res = requests.get(f"{BASE_URL}/api/queue")
    queue = res.json()
    found = any(r.get("report_id") == report_id for r in queue)
    if not found:
        print("FAIL: Report not found in queue after submission.")
        return
    print("PASS: Report successfully appeared in HSE Queue.")
    
    # 5. Test Review Action
    print("\n5. Testing HSE Review Action (Accept)...")
    action_data = {
        "report_id": report_id,
        "reviewer_name": "HSE001",
        "action": "Accept",
        "comments": "Automated e2e test acceptance"
    }
    res = requests.post(f"{BASE_URL}/api/review", json=action_data)
    if res.status_code != 200:
        print(f"FAIL: Review action failed: {res.text}")
        return
    print("PASS: Review action processed and Supabase updated.")
    
    # 6. Test Analytics
    print("\n6. Testing Analytics Dashboard...")
    res = requests.get(f"{BASE_URL}/api/analytics")
    if res.status_code != 200:
        print(f"FAIL: Analytics fetch failed: {res.text}")
        return
    stats = res.json()
    print(f"PASS: Analytics loaded successfully.")
    print(f"      Total Reports: {stats.get('total_reports')}")
    print(f"      Critical Priority: {stats.get('critical_count')}")
    
    print("\n--- ALL TESTS PASSED SUCCESSFULLY ---")

if __name__ == "__main__":
    run_tests()
