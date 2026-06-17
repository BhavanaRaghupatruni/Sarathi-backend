import requests
import json
import sys
import time

BASE_URL = "http://127.0.0.1:4000"

MOCK_SCHEME = {
    "scheme_name": "Aasara Senior Pension Scheme",
    "state": "Telangana",
    "category": "Pension",
    "description": "Financial assistance to support low income senior citizens in Telangana.",
    "benefits": {"amount": 2016, "frequency": "monthly"},
    "eligibility_rules": {
        "min_age": 60,
        "gender_allowed": ["any"],
        "max_income": 150000,
        "occupations": ["any"],
        "state": "Telangana"
    },
    "required_documents": ["Aadhaar Card", "Ration Card", "Income Certificate"],
    "application_process": "Submit application form online or at local Gram Panchayat/secretariat.",
    "source_page": 4,
    "verification_status": "VERIFIED"
}

CITIZEN_PROFILE = {
    "age": 62,
    "gender": "female",
    "state": "Telangana",
    "annualIncome": "80000",
    "mainOccupation": "agriculture",
    "doc_aadhaar_available": "YES",
    "doc_rationCard_available": "YES",
    "doc_incomeCert_available": "NO"  # Income Certificate missing
}

def verify_rag_flow():
    print("=== STARTING SAARTHI RAG & ELIGIBILITY VERIFICATION ===\n")
    
    # 1. Register a Scheme through Admin Endpoint
    print("[1] Admin Endpoint: Registering 'Aasara Senior Pension Scheme'...")
    try:
        res = requests.post(f"{BASE_URL}/admin/schemes", json=MOCK_SCHEME)
        if res.status_code in [200, 201]:
            print("Successfully registered scheme!")
            print(json.dumps(res.json(), indent=2))
        else:
            print(f"Error {res.status_code}: {res.text}")
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to backend at {BASE_URL}. Ensure uvicorn is running.")
        sys.exit(1)
        
    print("-" * 60)

    # 2. Ingest raw document content
    print("[2] Ingestion Endpoint: Uploading raw document text for boundary testing...")
    raw_ingest = {
        "title": "PM Ujjwala Yojana Guide",
        "content": "Scheme Name: PM Ujjwala Yojana\nState: Central\nCategory: Health\nDescription: Clean cooking fuel LPG connection for rural women.\nBenefits: Free LPG Gas cylinder connection.\nRequired Documents: Aadhaar Card, Ration Card\nApplication Process: Apply at local gas agency."
    }
    res = requests.post(f"{BASE_URL}/documents/raw-text", json=raw_ingest)
    print(f"Ingestion status: {res.status_code}")
    print(res.json())
    print("-" * 60)

    # 3. List ingested documents
    print("[3] Documents list check...")
    res = requests.get(f"{BASE_URL}/documents")
    print(f"Status: {res.status_code}")
    print(f"Ingested documents list count: {len(res.json())}")
    print("-" * 60)

    # 4. Trigger Chat flow completion (RAG + Eligibility Engine + LLM)
    chat_payload = {
        "session_id": "test_session_99",
        "profile": CITIZEN_PROFILE,
        "question": "Am I eligible for PM Ujjwala Yojana and what are the benefits?"
    }
    print("[4] Chat completions endpoint call (Evaluating profile against rules)...")
    start = time.time()
    res = requests.post(f"{BASE_URL}/chat/completions", json=chat_payload)
    latency = int((time.time() - start) * 1000)
    print(f"Status: {res.status_code}")
    print(f"Completions query latency: {latency}ms")
    
    if res.status_code == 200:
        data = res.json()
        print("\n--- DETERMINISTIC ENGINE RECOMMENDATIONS ---")
        for rec in data["recommendations"]:
            print(f"• Scheme: {rec['scheme_name']}")
            print(f"  Status: {rec['eligibility_status']} (Score: {rec['eligibility_score']})")
            print(f"  Why: {rec['why_recommended']}")
            print(f"  Missing Documents: {rec['missing_documents']}")
            print(f"  Next Steps: {rec['next_steps']}")
            
        print("\n--- RETRIEVED SOURCES ---")
        for idx, src in enumerate(data["retrieved_sources"]):
            print(f"[{idx+1}] Chunk Section: {src['section']} (Re-rank Score: {src['rerank_score']})")
            
        print("\n--- LLM GENERATED RESPONSE ---")
        print(data["response"])
    else:
        print(f"Completions endpoint error: {res.text}")
        
    print("\n=== VERIFICATION FINISHED ===")

if __name__ == "__main__":
    verify_rag_flow()
