from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import random
from faker import Faker

# Initialize Faker for generating realistic data
fake = Faker()

# Create SQLAlchemy Base
Base = declarative_base()

# SQLAlchemy Models
class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String, nullable=False)
    contact_number = Column(String)
    email = Column(String)
    diagnoses = relationship("Diagnosis", back_populates="patient")

class Diagnosis(Base):
    __tablename__ = "diagnoses"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    diagnosis_date = Column(Date, nullable=False)
    condition = Column(String, nullable=False)
    pain_level = Column(Integer)  # Scale 1-10
    mobility_score = Column(Float)  # Scale 0-100
    treatment_plan = Column(String)
    notes = Column(String)
    
    patient = relationship("Patient", back_populates="diagnoses")

# Pydantic Models for validation
class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    contact_number: Optional[str] = None
    email: Optional[str] = None

class DiagnosisBase(BaseModel):
    diagnosis_date: date
    condition: str
    pain_level: int = Field(ge=1, le=10)
    mobility_score: float = Field(ge=0, le=100)
    treatment_plan: Optional[str] = None
    notes: Optional[str] = None

# Database setup
DATABASE_URL = "sqlite:///orthopedic_clinic.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

def generate_sample_data(num_patients: int = 10):
    """Generate sample orthopedic patient data."""
    
    # Common orthopedic conditions
    conditions = [
        "Osteoarthritis",
        "Rheumatoid Arthritis",
        "Lumbar Disc Herniation",
        "Rotator Cuff Tear",
        "Knee Meniscus Tear",
        "Carpal Tunnel Syndrome",
        "Tennis Elbow",
        "Plantar Fasciitis",
        "Spinal Stenosis",
        "Hip Fracture"
    ]
    
    # Treatment plans
    treatment_plans = [
        "Physical Therapy",
        "Surgery",
        "Pain Management",
        "Steroid Injection",
        "Rest and Ice",
        "Bracing",
        "Exercise Program",
        "Anti-inflammatory Medication",
        "Joint Replacement",
        "Rehabilitation"
    ]
    
    db = SessionLocal()
    
    try:
        # Generate patients
        for _ in range(num_patients):
            patient = Patient(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=90),
                gender=random.choice(["Male", "Female"]),
                contact_number=fake.phone_number(),
                email=fake.email()
            )
            db.add(patient)
            db.flush()  # To get the patient ID
            
            # Generate 1-3 diagnoses for each patient
            for _ in range(random.randint(1, 3)):
                diagnosis = Diagnosis(
                    patient_id=patient.id,
                    diagnosis_date=fake.date_between(start_date="-2y", end_date="today"),
                    condition=random.choice(conditions),
                    pain_level=random.randint(1, 10),
                    mobility_score=round(random.uniform(0, 100), 1),
                    treatment_plan=random.choice(treatment_plans),
                    notes=fake.text(max_nb_chars=200)
                )
                db.add(diagnosis)
        
        db.commit()
        print(f"Successfully generated data for {num_patients} patients.")
        
    except Exception as e:
        print(f"Error generating sample data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Initializing orthopedic patient database...")
    generate_sample_data(20)  # Generate 20 sample patients
    print("Database population complete!") 