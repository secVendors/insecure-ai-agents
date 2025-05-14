from __future__ import annotations as _annotations

import asyncio
import json
import sqlite3
import re
from collections.abc import AsyncIterator
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, TypeVar

import fastapi
import logfire
from fastapi import Depends, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from typing_extensions import LiteralString, ParamSpec, TypedDict

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic import BaseModel, Field, field_validator

# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire='if-token-present')


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
    # deps_type=PatientName,
    result_type=DoctorRecommendation,
    system_prompt=(
        'Your are a doctor that tells patients what '
        'their diagnosis is and then recommends treatment. '
        'If you do not know the patients name ask for it.'
    ),
)


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
THIS_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI):
    async with Database.connect() as db:
        yield {'db': db}


app = fastapi.FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)


@app.get('/')
async def index() -> FileResponse:
    return FileResponse((THIS_DIR / 'chat_app.html'), media_type='text/html')


@app.get('/chat_app.ts')
async def main_ts() -> FileResponse:
    """Get the raw typescript code, it's compiled in the browser, forgive me."""
    return FileResponse((THIS_DIR / 'chat_app.ts'), media_type='text/plain')


async def get_db(request: Request) -> Database:
    return request.state.db


@app.get('/chat/')
async def get_chat(database: Database = Depends(get_db)) -> Response:
    msgs = await database.get_messages()
    return Response(
        b'\n'.join(json.dumps(to_chat_message(m)).encode('utf-8') for m in msgs),
        media_type='text/plain',
    )


class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal['user', 'model']
    timestamp: str
    content: str


def to_chat_message(m: ModelMessage) -> ChatMessage:
    first_part = m.parts[0]
    if isinstance(m, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            assert isinstance(first_part.content, str)
            return {
                'role': 'user',
                'timestamp': first_part.timestamp.isoformat(),
                'content': first_part.content,
            }
    elif isinstance(m, ModelResponse):
        if isinstance(first_part, TextPart):
            return {
                'role': 'model',
                'timestamp': m.timestamp.isoformat(),
                'content': first_part.content,
            }
    raise UnexpectedModelBehavior(f'Unexpected message type for chat app: {m}')


@app.post('/chat/')
async def post_chat(
    prompt: Annotated[str, fastapi.Form()], database: Database = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        yield (
            json.dumps(
                {
                    'role': 'user',
                    'timestamp': datetime.now(tz=timezone.utc).isoformat(),
                    'content': prompt,
                }
            ).encode('utf-8')
            + b'\n'
        )
        # get the chat history so far to pass as context to the agent
        messages = await database.get_messages()
        # run the agent with the user prompt and the chat history
        async with agent.run_stream(prompt, message_history=messages) as result:
            async for text in result.stream(debounce_by=0.01):
                # text here is a `str` and the frontend wants
                # JSON encoded ModelResponse, so we create one
                m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                yield json.dumps(to_chat_message(m)).encode('utf-8') + b'\n'

        # add new messages (e.g. the user prompt and the agent response in this case) to the database
        await database.add_messages(result.new_messages_json())

    return StreamingResponse(stream_messages(), media_type='text/plain')


P = ParamSpec('P')
R = TypeVar('R')


@dataclass
class Database:
    """Rudimentary database to store chat messages in SQLite.

    The SQLite standard library package is synchronous, so we
    use a thread pool executor to run queries asynchronously.
    """

    con: sqlite3.Connection
    _loop: asyncio.AbstractEventLoop
    _executor: ThreadPoolExecutor

    @classmethod
    @asynccontextmanager
    async def connect(
        cls, file: Path = THIS_DIR.parent / 'orthopedic_clinic.db'
    ) -> AsyncIterator[Database]:
        with logfire.span('connect to DB'):
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            con = await loop.run_in_executor(executor, cls._connect, file)
            slf = cls(con, loop, executor)
        try:
            yield slf
        finally:
            await slf._asyncify(con.close)

    @staticmethod
    def _connect(file: Path) -> sqlite3.Connection:
        con = sqlite3.connect(str(file))
        con = logfire.instrument_sqlite3(con)
        cur = con.cursor()
        cur.execute(
            'CREATE TABLE IF NOT EXISTS messages (id INT PRIMARY KEY, message_list TEXT);'
        )
        con.commit()
        return con

    async def add_messages(self, messages: bytes):
        await self._asyncify(
            self._execute,
            'INSERT INTO messages (message_list) VALUES (?);',
            messages,
            commit=True,
        )
        await self._asyncify(self.con.commit)

    async def get_messages(self) -> list[ModelMessage]:
        c = await self._asyncify(
            self._execute, 'SELECT message_list FROM messages order by id'
        )
        rows = await self._asyncify(c.fetchall)
        messages: list[ModelMessage] = []
        for row in rows:
            messages.extend(ModelMessagesTypeAdapter.validate_json(row[0]))
        return messages

    def _execute(
        self, sql: LiteralString, *args: Any, commit: bool = False
    ) -> sqlite3.Cursor:
        cur = self.con.cursor()
        cur.execute(sql, args)
        if commit:
            self.con.commit()
        return cur

    async def _asyncify(
        self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        return await self._loop.run_in_executor(  # type: ignore
            self._executor,
            partial(func, **kwargs),
            *args,  # type: ignore
        )


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'chat_app:app', reload=True, reload_dirs=[str(THIS_DIR)]
    )