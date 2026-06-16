import requests
import json
import sys

BASE_URL = "http://127.0.0.1:4000"

VALID_PAYLOAD = {
    # Section A
    "firstName": "John",
    "lastName": "Doe",
    "primaryMobile": "9876543210",
    "dob": "1990-01-01",
    "gender": "Male",
    "maritalStatus": "Married",
    "religion": "Hindu",
    "socialCategory": "General",
    "residentialStatus": "Permanent",
    "village": "Teerthanahalli",
    "district": "Shimoga",
    "state": "Karnataka",
    
    # Section B
    "familyStructure": "Nuclear",
    "familyMembers": [
        {
            "name": "Jane Doe",
            "relation": "Spouse",
            "age": "32",
            "gender": "Female",
            "education": "Graduate",
            "employment": "Self-employed",
            "income": "5000"
        }
    ],

    # Section C
    "mainOccupation": "Farmer",
    "employmentNature": "Self-employed",

    # Section D
    "monthlyIncomeRange": "5000-10000",
    "annualIncome": "80000",
    "bankAccount": "YES",

    # Section E
    "housingType": "Pucca",
    "housingOwnership": "Owned",
    "agriLand": "YES",
    "livestock": "YES",

    # Section I
    "hasSmartphone": "YES",

    # Section K
    "consentStatus": "AGREED",
    "signatureName": "John Doe",
    "consentDate": "2026-06-12",
    "surveyorName": "Alice Smith",
    "surveyorId": "S123",
    "surveyLocation": "Teerthanahalli",
    
    # Metadata
    "survey_language": "en",
    "submitted_at": "2026-06-12T05:45:12.123Z",
    "sections_visited": ["A", "B", "C", "D", "E", "I", "K"]
}

def test_endpoints():
    print("Starting backend endpoints verification...\n")
    
    # --- TEST 1: Submit valid payload ---
    print("[Test 1] POST /submit - Submitting a valid survey...")
    try:
        response = requests.post(f"{BASE_URL}/submit", json=VALID_PAYLOAD)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to backend at {BASE_URL}. Make sure uvicorn is running.")
        sys.exit(1)
        
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    
    data = response.json()
    record_id = data["id"]
    print(f"Successfully created survey record with ID: {record_id}")
    print(f"Returned database first name: {data['first_name']}, last name: {data['last_name']}")
    print("-" * 50)

    # --- TEST 2: Validation check with invalid payload ---
    print("[Test 2] POST /submit - Checking validation (missing required fields)...")
    invalid_payload = VALID_PAYLOAD.copy()
    del invalid_payload["firstName"]  # Missing required field
    response = requests.post(f"{BASE_URL}/submit", json=invalid_payload)
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 422, f"Expected 422 Unprocessable Entity, got {response.status_code}"
    print("Validation successfully caught the missing required field!")
    print("-" * 50)

    # --- TEST 3: Retrieve records ---
    print("[Test 3] GET /records - Fetching all records...")
    response = requests.get(f"{BASE_URL}/records")
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    records = response.json()
    print(f"Retrieved {len(records)} record(s).")
    assert any(r["id"] == record_id for r in records), "Created record not found in list"
    print("-" * 50)

    # --- TEST 4: Update record ---
    print(f"[Test 4] PUT /records/{record_id} - Updating first name to 'Jonathan'...")
    update_payload = {
        "firstName": "Jonathan",
        "lastName": "Doe"
    }
    response = requests.put(f"{BASE_URL}/records/{record_id}", json=update_payload)
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    updated_data = response.json()
    assert updated_data["first_name"] == "Jonathan", f"Expected 'Jonathan', got {updated_data['first_name']}"
    print(f"Successfully updated first name in database to: {updated_data['first_name']}")
    print("-" * 50)

    # --- TEST 5: Delete record ---
    print(f"[Test 5] DELETE /records/{record_id} - Deleting the record...")
    response = requests.delete(f"{BASE_URL}/records/{record_id}")
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 204, f"Expected 204 No Content, got {response.status_code}"
    
    # Confirm deletion
    get_response = requests.get(f"{BASE_URL}/records/{record_id}")
    print(f"GET deleted record check status code: {get_response.status_code}")
    assert get_response.status_code == 404, f"Expected 404 for deleted record, got {get_response.status_code}"
    print("Record successfully deleted!")
    print("-" * 50)
    
    print("\nALL ENDPOINT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_endpoints()
