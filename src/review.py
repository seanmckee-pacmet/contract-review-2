import os
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import json
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from typing import List, Dict, Tuple, Any
import time
import traceback
from src.get_formatted_text import get_formatted_text, parse_document
from tenacity import retry, stop_after_attempt, wait_exponential
import concurrent.futures
from pydantic import BaseModel
import functools

# Load environment variables
load_dotenv()

# Set up OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The embedding model name
embedding_model_name = "text-embedding-3-small"

# Pydantic models for responses
class POAnalysisResponse(BaseModel):
    all_invoked: bool
    clause_identifiers: List[str]
    requirements: List[str]

class DocumentTypeResponse(BaseModel):
    document_type: str

class ClauseSimilarityResponse(BaseModel):
    is_similar: bool

class Quote(BaseModel):
    clause: str
    quote: str
    document_type: str

class ClauseAnalysisResponse(BaseModel):
    clause: str
    invoked: str
    quotes: List[Quote]

# Caching decorator
def memoize(func):
    cache = {}
    @functools.wraps(func)
    def memoized_func(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return memoized_func

@memoize
def chunk_markdown_text(markdown_text):
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    initial_chunks = splitter.split_text(markdown_text)

    sub_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )

    final_chunks = []
    for chunk in initial_chunks:
        if len(chunk.page_content) > 1000:
            sub_chunks = sub_splitter.split_text(chunk.page_content)
            for sub_chunk in sub_chunks:
                final_chunks.append({
                    "page_content": sub_chunk,
                    "metadata": chunk.metadata
                })
        else:
            final_chunks.append({
                "page_content": chunk.page_content,
                "metadata": chunk.metadata
            })

    return final_chunks

@memoize
def create_embeddings(chunks: List[Dict], batch_size: int = 100) -> List[List[float]]:
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        batch_texts = [chunk['page_content'] for chunk in batch]
        
        try:
            response = openai_client.embeddings.create(
                input=batch_texts,
                model=embedding_model_name
            )
            batch_embeddings = [data.embedding for data in response.data]
            all_embeddings.extend(batch_embeddings)
            
            print(f"Processed batch {i//batch_size + 1} of {(len(chunks)-1)//batch_size + 1}")
            
            time.sleep(1)
        except Exception as e:
            print(f"Error processing batch {i//batch_size + 1}: {str(e)}")
    
    return all_embeddings

def initialize_qdrant(collection_name: str, vector_size: int):
    client = QdrantClient(
        url="https://50238ac6-e670-42be-933e-c836f812c16e.europe-west3-0.gcp.cloud.qdrant.io", 
        api_key=os.getenv("QDRANT_API_KEY"),
    )
    
    collections = client.get_collections().collections
    if not any(collection.name == collection_name for collection in collections):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    return client

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def upsert_with_retry(client, collection_name, batch):
    try:
        client.upsert(
            collection_name=collection_name,
            points=batch
        )
    except Exception as e:
        print(f"Error during upsert: {str(e)}")
        raise

def store_embeddings_in_qdrant(client: QdrantClient, collection_name: str, chunks: List[Dict], embeddings: List[List[float]]):
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        points.append(PointStruct(
            id=i,
            vector=embedding,
            payload={
                "content": chunk["page_content"],
                "metadata": chunk["metadata"]
            }
        ))
    
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]
        try:
            upsert_with_retry(client, collection_name, batch)
            print(f"Uploaded batch {i//batch_size + 1} of {(len(points)-1)//batch_size + 1}")
        except Exception as e:
            print(f"Failed to upload batch {i//batch_size + 1} after multiple retries: {str(e)}")

@memoize
def load_notable_clauses() -> Dict[str, Dict[str, Any]]:
    with open('notable_clauses.json', 'r') as f:
        return json.load(f)

def query_qdrant_for_clauses(client: QdrantClient, collection_name: str, clause: str, description: str, top_k: int = 5) -> List[Dict]:
    # Combine clause and description for a more comprehensive query
    query = f"{clause}: {description}"
    
    query_vector = openai_client.embeddings.create(input=query, model=embedding_model_name).data[0].embedding
    search_result = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k
    )
    return [
        {
            "score": hit.score, 
            "content": hit.payload["content"], 
            "metadata": hit.payload["metadata"],
            "document_type": hit.payload["metadata"]["document_type"]
        } 
        for hit in search_result
    ]

def is_clause_similar(clause, invoked_clauses):
    if not invoked_clauses:
        return False
    
    prompt = f"""
    Compare the following clause identifier with the list of invoked clauses:
    
    Clause to check: {clause}
    
    Invoked clauses:
    {json.dumps(invoked_clauses, indent=2)}
    
    Is the clause to check similar to any of the invoked clauses? Consider variations in naming, formatting, or abbreviations.
    """
    
    response = openai_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are an expert in comparing legal clause identifiers."},
            {"role": "user", "content": prompt}
        ],
        response_format=ClauseSimilarityResponse
    )
    
    return response.choices[0].message.parsed.is_similar

def is_clause_invoked(clause, invoked_clauses, all_invoked):
    if all_invoked:
        return True
    return any(
        invoked.strip().upper() == clause.strip().upper() or
        (invoked.strip().upper() in clause.strip().upper() and len(invoked) > 3)
        for invoked in invoked_clauses
    )

def clear_qdrant_database(client: QdrantClient, collection_name: str):
    try:
        client.delete_collection(collection_name=collection_name)
        print(f"Qdrant collection '{collection_name}' has been deleted successfully.")
    except Exception as e:
        print(f"Error clearing Qdrant collection '{collection_name}': {str(e)}")

def determine_document_type(content: str) -> str:
    prompt = f"""
    Analyze the following text and determine if it is a Purchase Order, Quality Document, or Terms and Conditions.
    Respond with only one of these three options or "Unknown" if you can't determine.
    
    Text sample:
    {content[:2000]}  # Using the first 2000 characters as a sample
    """

    response = openai_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are an expert at identifying document types."},
            {"role": "user", "content": prompt}
        ],
        response_format=DocumentTypeResponse
    )

    return response.choices[0].message.parsed.document_type

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
    {content[:4000]}  # Using the first 4000 characters as a sample
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

def process_document(file_path):
    content = parse_document(file_path)
    print(f"[DEBUG] Document content for {file_path}:\n{content[:500]}...")  # First 500 chars

    doc_type = determine_document_type(content)
    print(f"[DEBUG] Determined document type for {file_path}: {doc_type}")

    chunks = chunk_markdown_text(content)
    print(f"[DEBUG] Created {len(chunks)} chunks for {file_path}")
    
    for chunk in chunks:
        chunk['metadata']['document_type'] = doc_type
    
    embeddings = create_embeddings(chunks)
    print(f"[DEBUG] Created {len(embeddings)} embeddings for {file_path}")
    
    po_analysis = None
    if doc_type == "Purchase Order":
        po_analysis = review_po(content)
        print(f"[DEBUG] PO Analysis for {file_path}:\n{po_analysis}")
    
    return file_path, doc_type, chunks, embeddings, po_analysis

def review_documents(file_paths: List[str], company_name: str) -> Dict[str, Any]:
    print(f"Clause Analysis for {company_name}\n")

    print(f"[DEBUG] Starting review for company: {company_name}")
    print(f"[DEBUG] Files to process: {file_paths}")

    collection_name = f"{company_name}_documents"
    vector_size = 1536  # Size for text-embedding-3-small
    qdrant_client = initialize_qdrant(collection_name, vector_size)
    print(f"[DEBUG] Initialized Qdrant collection: {collection_name}")

    all_chunks = []
    all_embeddings = []
    document_types = {}
    po_analysis = None
    invoked_clauses = []
    all_invoked = False

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_document, file_path) for file_path in file_paths]
        for future in concurrent.futures.as_completed(futures):
            try:
                file_path, doc_type, chunks, embeddings, doc_po_analysis = future.result()
                document_types[file_path] = doc_type
                all_chunks.extend(chunks)
                all_embeddings.extend(embeddings)
                
                if doc_type == "Purchase Order" and doc_po_analysis:
                    po_analysis = doc_po_analysis
                    all_invoked = po_analysis.all_invoked
                    invoked_clauses = po_analysis.clause_identifiers
                
                print(f"[DEBUG] Processed {file_path}: {len(chunks)} chunks created, doc_type: {doc_type}")
                if doc_po_analysis:
                    print(f"[DEBUG] PO Analysis for {file_path}: all_invoked={all_invoked}, invoked_clauses={invoked_clauses}")
            except Exception as e:
                print(f"[DEBUG] Error processing {file_path}: {str(e)}")
                print("[DEBUG] Full traceback:")
                traceback.print_exc()

    print(f"[DEBUG] Total chunks: {len(all_chunks)}, Total embeddings: {len(all_embeddings)}")
    store_embeddings_in_qdrant(qdrant_client, collection_name, all_chunks, all_embeddings)
    print(f"[DEBUG] Stored embeddings in Qdrant collection: {collection_name}")

    notable_clauses = load_notable_clauses()
    print(f"[DEBUG] Loaded notable clauses structure")

    results = []

    for category, category_data in notable_clauses.items():
        for clause, description in category_data['clauses'].items():
            print(f"\nAnalyzing clause: {clause}")
            print(f"Description: {description}")
            
            clause_results = query_qdrant_for_clauses(qdrant_client, collection_name, clause, description)
            print(f"Found {len(clause_results)} relevant text chunks for clause: {clause}")
            
            # Print all the clause results
            for i, result in enumerate(clause_results, 1):
                print(f"Result {i}:")
                print(f"Score: {result['score']}")
                print(f"Content: {result['content']}")
                print(f"Document Type: {result['document_type']}")
                print("---")
            
            prompt = f"""
            Given the following information:

            Clause: {clause}
            Description: {description}

            Relevant text chunks:
            {json.dumps(clause_results, indent=2)}

            Purchase Order Analysis:
            po_invokes_all_clauses: {all_invoked}
            invoked_clauses: {json.dumps(invoked_clauses)}

            Task:
            1. Determine if the clause is invoked based on the following rules:
            - First determine if the chunk is relevant and invokes the clause by comparing the chunk to the clause and clause description
            - If the document type is a Quality Document AND
                po_invokes_all_clauses is false AND
                the clause is in invoked_clauses
                Then the clause is invoked
            - If the document type is a Quality Document AND
                po_invokes_all_clauses is false AND
                the clause is not in invoked_clauses
                Then the clause is not invoked
            - Otherwise, the clause is invoked

            2. If the clause is invoked, analyze ALL provided text chunks to find quotes that provide valuable information relating to the clause or its description.
            - Include ALL relevant and informative quotes from the provided text chunks.
            - Only disregard quotes that are completely irrelevant or do not add any value to understanding the clause's application.

            3. Format your response as a JSON object with the following structure:
            {{
                "clause": "{clause}",
                "invoked": "Yes" or "No",
                "quotes": [
                    {{
                        "clause": "Clause ID",
                        "quote": "Relevant quote text",
                        "document_type": "Type of document containing the quote"
                    }},
                    ...
                ]
            }}

            Important notes:
            - If the clause is not invoked, set "invoked" to "No" and return an empty list for "quotes".
            - Only include the "quotes" field if the clause is invoked.
            - Ensure all JSON fields are properly escaped.
            - Include ALL relevant quotes from the provided text chunks.

            Please analyze ALL given information and provide your response in the specified JSON format.
            """
            
            print("Sending prompt to OpenAI for clause analysis")
            # print(f"Prompt: {prompt}")
            
            response = openai_client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
                    {"role": "user", "content": prompt}
                ],
                response_format=ClauseAnalysisResponse
            )
            
            analysis = response.choices[0].message.parsed
            print(f"Received analysis for clause {clause}: invoked={analysis.invoked}, quotes={len(analysis.quotes)}")
            
            if analysis.invoked == 'Yes':
                results.append(analysis.model_dump())
                print(f"Clause {clause} is invoked. Added to results.")
                # for quote in analysis.quotes:
                #     print(f"Quote: {quote['quote']} (Document Type: {quote['document_type']})")
            else:
                print(f"Clause {clause} is not invoked. Skipped.")

    print(f"Review completed. Total results: {len(results)}")
    return {
        "company_name": company_name,
        "po_analysis": po_analysis.model_dump() if po_analysis else None,
        "clause_analysis": results
    }

# Example usage
if __name__ == "__main__":
    file_paths = ["path/to/document1.pdf", "path/to/document2.docx"]
    company_name = "Example Company"
    review_results = review_documents(file_paths, company_name)
    print(json.dumps(review_results, indent=2))