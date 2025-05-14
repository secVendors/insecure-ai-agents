from pydantic_ai import Agent, RunContext
import asyncio
import argparse
import sqlite3
from pydantic import BaseModel, Field, field_validator
import re
import nest_asyncio
import logfire

logfire.configure()
nest_asyncio.apply()


class PatientName(BaseModel):
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        # Remove any leading/trailing whitespace
        v = v.strip()

        # Check if the name contains only valid characters
        if not re.match(r'^[a-zA-Z\- ]+$', v):
            raise ValueError("Name must contain only letters, hyphens, and spaces")

        return v

    @classmethod
    def from_full_name(cls, full_name: str) -> "PatientName":
        if not isinstance(full_name, str) or not full_name.strip():
            raise ValueError("Full name must be a non-empty string")

        parts = full_name.strip().split()
        if len(parts) < 2:
            raise ValueError("Both first and last name are required")

        return cls(
            first_name=parts[0],
            last_name=parts[-1]
        )


class PatientDiagnosis(BaseModel):
    id: int
    first_name: str
    last_name: str
    diagnosis_date: str
    condition: str
    pain_level: int
    treatment_plan: str


class DoctorRecommendation(PatientDiagnosis):
    message: str


agent = Agent(
    'openai:gpt-4o',
    deps_type=PatientName,
    result_type=DoctorRecommendation,
    system_prompt=(
        'Your are a doctor that tells patients what '
        'their diagnosis is and then recommends treatment.'
    ),
)
Agent.instrument_all()


@agent.tool
def get_patient_diagnosis(patient: RunContext[PatientName]) -> DoctorRecommendation:
    """Get the patient's diagnosis."""
    conn = sqlite3.connect("orthopedic_clinic.db")
    conn.row_factory = sqlite3.Row

    try:
        patient_query = """
                SELECT 
                    id
                FROM patients
                WHERE first_name = ? AND last_name = ?
                """
        cursor = conn.cursor()
        cursor.execute(patient_query, (patient.deps.first_name, patient.deps.last_name))

        results = cursor.fetchone()
        if results is None:
            raise ValueError(f"No patient found with name: {patient.deps.first_name} {patient.deps.name.last_name}")

        patient_id = results[0]

        query = """
        SELECT 
            p.id,
            p.first_name,
            p.last_name,
            d.diagnosis_date,
            d.condition,
            d.pain_level,
            d.treatment_plan
        FROM diagnoses d
        JOIN patients p ON p.id = d.patient_id
        WHERE p.id = ?
        ORDER BY d.diagnosis_date DESC
        """

        cursor = conn.cursor()
        cursor.execute(query, (patient_id,))

        patient_info = [dict(row) for row in cursor.fetchall()]
        if not patient_info:
            raise ValueError(f"No diagnoses found for patient with ID: {patient_id}")

        # Validate the diagnosis data using Pydantic
        diagnosis = PatientDiagnosis(**patient_info[0])
        doctor_rec = DoctorRecommendation(**diagnosis.model_dump(), message="")
        return doctor_rec

    finally:
        conn.close()


async def run_agent(patient_name: PatientName):
    async with agent.iter('What do you recommend for this patient?', deps=patient_name) as agent_run:
        async for node in agent_run:
            print(node)

        if agent_run.result and agent_run.result.data:
            print("Result:", agent_run.result.data)
        else:
            print("No result data available")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('patient1')
    parser.add_argument('patient2')
    args = parser.parse_args()
    patient_full_name_1 = PatientName.from_full_name(args.patient1)
    patient_full_name_2 = PatientName.from_full_name(args.patient2)

    try:
        asyncio.run(run_agent(patient_full_name_1))
        print("\n")
        asyncio.run(run_agent(patient_full_name_2))
    except KeyboardInterrupt:
        print("\nExecution interrupted by user")
    except Exception as e:
        print(f"Error running agent: {str(e)}")