import sqlite3
from datetime import datetime
from typing import List, Dict, Any

def connect_db() -> sqlite3.Connection:
    """Create a connection to the database."""
    return sqlite3.connect("orthopedic_clinic.db")

def get_patient_by_id(patient_id: int) -> Dict[str, Any]:
    """Fetch a patient and their diagnoses by ID."""
    conn = connect_db()
    conn.row_factory = sqlite3.Row  # This enables column access by name
    
    try:
        # Get patient details
        patient_query = """
        SELECT 
            p.id,
            p.first_name,
            p.last_name,
            p.date_of_birth,
            p.gender,
            p.contact_number,
            p.email
        FROM patients p
        WHERE p.id = ?
        """
        
        # Get patient's diagnoses
        diagnoses_query = """
        SELECT 
            d.diagnosis_date,
            d.condition,
            d.pain_level,
            d.mobility_score,
            d.treatment_plan,
            d.notes
        FROM diagnoses d
        WHERE d.patient_id = ?
        ORDER BY d.diagnosis_date DESC
        """
        
        cursor = conn.cursor()
        
        # Execute patient query
        cursor.execute(patient_query, (patient_id,))
        patient_data = dict(cursor.fetchone() or {})
        
        if not patient_data:
            return {}
        
        # Execute diagnoses query
        cursor.execute(diagnoses_query, (patient_id,))
        diagnoses = [dict(row) for row in cursor.fetchall()]
        
        # Add diagnoses to patient data
        patient_data['diagnoses'] = diagnoses
        
        return patient_data
        
    finally:
        conn.close()

def search_patients(search_term: str) -> List[Dict[str, Any]]:
    """Search patients by name or email."""
    conn = connect_db()
    conn.row_factory = sqlite3.Row
    
    try:
        query = """
        SELECT 
            p.id,
            p.first_name,
            p.last_name,
            p.date_of_birth,
            p.gender,
            p.email
        FROM patients p
        WHERE p.first_name LIKE ? 
           OR p.last_name LIKE ?
           OR p.email LIKE ?
        ORDER BY p.last_name, p.first_name
        """
        
        cursor = conn.cursor()
        search_pattern = f"%{search_term}%"
        cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        
        return [dict(row) for row in cursor.fetchall()]
        
    finally:
        conn.close()

def get_recent_diagnoses(days: int = 30) -> List[Dict[str, Any]]:
    """Get recent diagnoses with patient information."""
    conn = connect_db()
    conn.row_factory = sqlite3.Row
    
    try:
        query = """
        SELECT 
            p.id as patient_id,
            p.first_name,
            p.last_name,
            d.diagnosis_date,
            d.condition,
            d.pain_level,
            d.treatment_plan
        FROM diagnoses d
        JOIN patients p ON p.id = d.patient_id
        WHERE d.diagnosis_date >= date('now', ?)
        ORDER BY d.diagnosis_date DESC
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (f"-{days} days",))
        
        return [dict(row) for row in cursor.fetchall()]
        
    finally:
        conn.close()

if __name__ == "__main__":
    # Example usage
    print("\n1. Fetching patient by ID (example with ID 1):")
    patient = get_patient_by_id(1)
    if patient:
        print(f"\nPatient: {patient['first_name']} {patient['last_name']}")
        print(f"DOB: {patient['date_of_birth']}")
        print(f"Contact: {patient['email']}")
        print("\nDiagnoses:")
        for diagnosis in patient['diagnoses']:
            print(f"- {diagnosis['diagnosis_date']}: {diagnosis['condition']}")
            print(f"  Treatment: {diagnosis['treatment_plan']}")
    else:
        print("Patient not found")

    print("\n2. Searching for patients (example search 'john'):")
    search_results = search_patients("john")
    for patient in search_results:
        print(f"- {patient['first_name']} {patient['last_name']} ({patient['email']})")

    print("\n3. Recent diagnoses (last 30 days):")
    recent = get_recent_diagnoses(30)
    for record in recent:
        print(f"- {record['diagnosis_date']}: {record['first_name']} {record['last_name']}")
        print(f"  Condition: {record['condition']}")
        print(f"  Treatment: {record['treatment_plan']}") 