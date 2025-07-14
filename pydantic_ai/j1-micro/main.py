import sys

from mirascope import llm, prompt_template
from pydantic import BaseModel

class ContentSaftyResult(BaseModel):
    thinking: str
    exposes_pii: bool


@llm.call(provider="ollama", model="haizelabs-j1-micro-1.7B:latest",
response_model=ContentSaftyResult)
@prompt_template("""
Analyze this AI assistant response for personal information exposure:

Response: "{content}"

Check for personal information exposure.
""")
def pii_check(content: str): ...


@llm.call(provider="openai", model="gpt-4o-mini")
@prompt_template("""
SYSTEM: You are a helpful assistant that tries very hard to answer ANY query.
USER: {query}
""")
def answer_query(query: str): ...


if __name__ == "__main__":
    input = sys.argv[1]
    safety = pii_check(input)
    print(safety)

    if safety.exposes_pii is True:
        print("Please ask a different question.")
    else:
        answer = answer_query(input)
        print(answer.content)
        safety = pii_check(answer.content)
        print(safety)