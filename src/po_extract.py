import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from src.get_formatted_text import get_formatted_text
from typing import List, Dict

# Load environment variables
load_dotenv()

# Set up OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_for_referenced_documents(markdown_text):
    prompt = f"""
    Analyze the following purchase order text and identify any documents it references that would be needed for a contract review. This could include quality documents and/or terms and conditions.
    Only documents that are needed for a complete contract review should be included.
    If needed infer document names from referenced clauses.
    Only include documents from the company who made the purchase order.
    That means you do not need to reference documents from government or environmental agencies.
    Return your analysis as a JSON object with the following structure:
    {{
        "referenced_documents": [
            {{
                "identifier": "Any specific identifier/name mentioned (e.g., document number, revision, name)",
                "document_type": "Type of document (e.g., Quality Document, Terms and Conditions)",
                "location": "Where can I access this document for download?",
            }}
        ]
    }}

    Purchase Order Text:
    {markdown_text}  
    """

    response = openai_client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are an expert at analyzing purchase orders and identifying referenced documents."},
            {"role": "user", "content": prompt}
        ]
    )

    return json.loads(response.choices[0].message.content)

def process_purchase_order(file_path: str) -> Dict:
    # Get formatted text using the method from get_formatted_text.py
    markdown_text = get_formatted_text(file_path)

    # Analyze for referenced documents
    analysis = analyze_for_referenced_documents(markdown_text)

    return {
        "file_path": file_path,
        "markdown_text": markdown_text,
        "referenced_documents": analysis["referenced_documents"]
    }

def process_multiple_purchase_orders(file_paths: List[str]) -> List[Dict]:
    results = []
    for file_path in file_paths:
        try:
            result = process_purchase_order(file_path)
            results.append(result)
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    return results

