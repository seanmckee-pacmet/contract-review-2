from pydantic import BaseModel
from typing import List
from openai import OpenAI
import os

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class POAnalysisResponse(BaseModel):
    all_invoked: bool
    clause_identifiers: List[str]
    requirements: List[str]

def review_po(content: str) -> POAnalysisResponse:
    prompt = f"""
    Analyse this purchase order carefully and determine the following:
             1. If the entire quality document is invoked in this purchase order.
             2. If not, identify specific clause identifiers for the quality document that are invoked.
             3. Any other requirements noted on the purchase order.

             Correct any OCR errors in clause identifiers as previously instructed.
             
             Only Respond with the json and no other text or else I will get an error

              This json is going to be accessed by another function so please format it accordingly and include no other text but the json.
             Correct the following OCR-extracted text for invoked clauses. The OCR may introduce errors and misread characters. Use patterns to correct the text by identifying similarities with other clauses near the error. Additionally, if any ranges are listed (e.g., "1-7"), expand the range to list each clause individually. Clauses and ranges can be formatted in any way, such as numeric, alphanumeric, or with mixed patterns. Make sure to infer patterns from nearby clauses if necessary to fix OCR errors.

                Examples:
                Incorrect: "WOQRI-WQRI17"
                Correct: "WQR1, WQR2, WQR3, WQR4, WQR5, WQR6, WQR7, WQR8, WQR9, WQR10, WQR11, WQR12, WQR13, WQR14, WQR15, WQR16, WQR17"
                Note: Use the correct pattern "WQR" based on nearby clauses.

                Incorrect: "Clause A1.3, A1.5-A1.9, B2.1"
                Correct: "Clause A1.3, A1.5, A1.6, A1.7, A1.8, A1.9, B2.1"

                Incorrect: "WQR39, WRQ42-44"
                Correct: "WQR39, WQR42, WQR43, WQR44"
                Note: The pattern "WQR" should be used for consistency based on nearby clauses.

                Incorrect: "Clause 1, 2, 4-6"
                Correct: "Clause 1, 2, 4, 5, 6"

                Incorrect: "Subsection a.1-a.4, b.2"
                Correct: "Subsection a.1, a.2, a.3, a.4, b.2"

                Incorrect: "Item 1A-B3"
                Correct: "Item 1A, 1B, 2A, 2B, 3A, 3B"
                Note: Use the alphanumeric pattern consistently based on nearby clauses.

                Incorrect: "Clause X9-X12, Y1, Y4-Y5"
                Correct: "Clause X9, X10, X11, X12, Y1, Y4, Y5"

                Incorrect: "Section 1a-1c, 2b"
                Correct: "Section 1a, 1b, 1c, 2b"

                Use nearby clause patterns where necessary to correct OCR errors, ensuring that all ranges are expanded.
             
                Only Respond with the json and no other text or else I will get an error

    Purchase Order:
    {content}
    """

    response = openai_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
            {"role": "user", "content": prompt}
        ],
        response_format=POAnalysisResponse
    )

    return response.choices[0].message.parsed
