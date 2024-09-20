from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
import os
import asyncio

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class Quote(BaseModel):
    quote: str
    document_type: str
    header: str
    requires_human_review: str  

class ClauseAnalysisResponse(BaseModel):
    clause: str
    invoked: str
    quotes: List[Quote]

async def analyze_clauses_batch(client: OpenAI, prompts: List[str]) -> List[ClauseAnalysisResponse]:
    def process_batch(prompt):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
                    {"role": "user", "content": prompt}
                ],
                response_format=ClauseAnalysisResponse
            )
            return completion.choices[0].message.parsed
        except Exception as e:
            print(f"Error processing batch: {str(e)}")
            return None

    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, process_batch, prompt) for prompt in prompts]
    return await asyncio.gather(*tasks)