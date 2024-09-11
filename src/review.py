from pydantic import BaseModel
from typing import List, Dict, Optional
from openai import OpenAI

import os
from dotenv import load_dotenv
from openai import OpenAI
import qdrant_client
from qdrant_client.models import VectorParams, Distance, PointStruct
import json
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from typing import List, Dict, Tuple, Any
import time
from qdrant_client import QdrantClient
import traceback
from src.get_formatted_text import get_formatted_text, parse_document
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv()

# set up OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The embedding model name (to be used when making embedding calls)
embedding_model_name = "text-embedding-3-small"

#connect to LLM
openai = OpenAI()

# chunk markdown text by '#' indentifier using langchian markdown header splitter
def chunk_markdown_text(markdown_text):
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    initial_chunks = splitter.split_text(markdown_text)

    # Initialize RecursiveCharacterTextSplitter for further splitting
    sub_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )

    final_chunks = []
    for chunk in initial_chunks:
        if len(chunk.page_content) > 1000:
            # Split the chunk further
            sub_chunks = sub_splitter.split_text(chunk.page_content)
            for sub_chunk in sub_chunks:
                final_chunks.append({
                    "page_content": sub_chunk,
                    "metadata": chunk.metadata  # Maintain the original metadata
                })
        else:
            final_chunks.append({
                "page_content": chunk.page_content,
                "metadata": chunk.metadata
            })

    return final_chunks


# Add this new function to create embeddings
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
            
            # Add a small delay to avoid hitting rate limits
            time.sleep(1)
        except Exception as e:
            print(f"Error processing batch {i//batch_size + 1}: {str(e)}")
            # You might want to implement retry logic here
    
    return all_embeddings

# Add this function to initialize Qdrant client and create collection
def initialize_qdrant(collection_name: str, vector_size: int):
    client = QdrantClient(
    url="https://50238ac6-e670-42be-933e-c836f812c16e.europe-west3-0.gcp.cloud.qdrant.io", 
    api_key=os.getenv("QDRANT_API_KEY"),
)
    
    # Check if collection exists, if not create it
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
    
    # Upsert points in batches
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]
        try:
            upsert_with_retry(client, collection_name, batch)
            print(f"Uploaded batch {i//batch_size + 1} of {(len(points)-1)//batch_size + 1}")
        except Exception as e:
            print(f"Failed to upload batch {i//batch_size + 1} after multiple retries: {str(e)}")
            # You might want to implement some error handling or logging here

# Add these functions to load notable clauses and query Qdrant for clauses
def load_notable_clauses() -> Dict[str, str]:
    with open('notable_clauses.json', 'r') as f:
        return json.load(f)

def query_qdrant_for_clauses(client: QdrantClient, collection_name: str, query: str, top_k: int = 10) -> List[Dict]:
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

# Define Pydantic models for responses
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

# scan Tiff file which is the purchase order and use open ai to determine if there are specific clauses invoked from quality document or if there are any notable clauses
# params: po_markdown - markdown from the tiff file
def review_po(po_markdown):
    response = openai_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
            {"role": "user", "content": '''
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
             ''' + po_markdown}
        ],
        response_format=POAnalysisResponse,
    )
    
    return response.choices[0].message.parsed

# determine the type of each document (po/tc/qc)
def determine_document_type(text: str) -> str:
    sample = text[:2000]
    prompt = f"""
    Analyze the following text and determine if it is a Purchase Order, Quality Document, or Terms and Conditions.
    Respond with only one of these three options or "Unknown" if you can't determine.
    
    Text sample:
    {sample}
    """

    response = openai_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are an expert at identifying document types."},
            {"role": "user", "content": prompt}
        ],
        response_format=DocumentTypeResponse,
    )

    return response.choices[0].message.parsed.document_type

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
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert in comparing legal clause identifiers."},
            {"role": "user", "content": prompt}
        ],
        response_format=ClauseSimilarityResponse,
    )
    
    return response.choices[0].message.parsed.is_similar

def is_clause_invoked(clause, invoked_clauses, all_invoked):
    if all_invoked:
        return True
    return any(invoked.strip().upper() == clause.strip().upper() for invoked in invoked_clauses)

def review_documents(file_paths: List[str], company_name: str) -> Dict[str, Any]:
    # Initialize Qdrant client
    collection_name = f"{company_name}_documents"
    vector_size = 1536  # Size for text-embedding-3-small
    qdrant_client = initialize_qdrant(collection_name, vector_size)

    all_chunks = []
    all_embeddings = []
    document_types = {}
    po_analysis = None
    invoked_clauses = []
    all_invoked = False
    tc_content = ""

    # Process each document
    for file_path in file_paths:
        try:
            content = parse_document(file_path)  # Use parse_document from get_formatted_text.py
            print(f"Processing file: {file_path}")
            
            # Determine document type
            doc_type = determine_document_type(content)
            document_types[file_path] = doc_type
            print(f"Document type: {doc_type}")
            
            # If it's a Purchase Order, review it
            if doc_type == "Purchase Order":
                po_analysis = review_po(content)
                print("Purchase Order Analysis:")
                print(po_analysis)
                
                all_invoked = po_analysis.all_invoked
                invoked_clauses = po_analysis.clause_identifiers
            elif doc_type == "Terms and Conditions":
                tc_content = content
            
            chunks = chunk_markdown_text(content)
            
            # Add document type to metadata
            for chunk in chunks:
                chunk['metadata']['document_type'] = doc_type
            
            embeddings = create_embeddings(chunks)
            
            all_chunks.extend(chunks)
            all_embeddings.extend(embeddings)
            
            print(f"Processed {file_path}: {len(chunks)} chunks created")
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()

    # Store all embeddings in Qdrant
    store_embeddings_in_qdrant(qdrant_client, collection_name, all_chunks, all_embeddings)

    # Query for notable clauses
    notable_clauses = load_notable_clauses()
    results = []

    for clause, description in notable_clauses.items():
        print(f"\nAnalyzing clause: {clause}")
        clause_results = query_qdrant_for_clauses(qdrant_client, collection_name, clause)
        print(f"Found {len(clause_results)} relevant text chunks")
        
        # Prepare the prompt for OpenAI
        prompt = f"""
        Clause: {clause}
        Description: {description}
        
        Relevant text chunks:
        {json.dumps(clause_results, indent=2)}
        
        Purchase Order Analysis:
        All clauses invoked: {po_analysis.all_invoked}
        Specific clauses invoked: {json.dumps(po_analysis.clause_identifiers)}
        
        Based on the above information, analyze this clause with the following instructions:
        1. If 'All clauses invoked' is True, analyze this clause for all document types.
        2. If 'All clauses invoked' is False:
           a. For Quality Control (QC) documents: only analyze this clause if it exactly matches (ignoring case) one of the 'Specific clauses invoked'.
           
           b. For Terms and Conditions (TC) documents: always analyze this clause.
           c. For Purchase Order (PO) documents: always analyze this clause.
        3. When including quotes, only use quotes from the appropriate document type based on the above rules.
        4. Always include the document type for each quote.
        
        If the clause should not be analyzed based on these criteria, respond with {{"invoked": "No", "quotes": []}}.
        
        If the clause should be analyzed, determine if it's invoked in the document and return a JSON object with the following structure:
        {{
            "clause": "{clause}",
            "invoked": "Yes/No",
            "quotes": [
                {{"clause": "Clause ID", "quote": "Quote Text", "document_type": "Document Type"}},
                {{"clause": "Clause ID", "quote": "Quote Text", "document_type": "Document Type"}},
                ...
            ]
        }}
        
        Note: Only include quotes if the clause is invoked. If not invoked, return an empty list for quotes.
        """
        
        print("Sending prompt to OpenAI for analysis")
        # Call OpenAI for analysis
        response = openai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
                {"role": "user", "content": prompt}
            ],
            response_format=ClauseAnalysisResponse,
        )
        
        analysis = response.choices[0].message.parsed
        if analysis.invoked == 'Yes':
            results.append(analysis.model_dump())
            print(f"Clause {clause} is invoked. Added to results.")
        else:
            print(f"Clause {clause} is not invoked. Skipped.")

    print("\nFinal results:")
    print("company name: ", company_name)
    print("document types: ", document_types)
    print("po analysis: ", po_analysis)
    print("clause analysis:")
    for result in results:
        print(f"\nClause: {result['clause']}")
        print(f"Invoked: {result['invoked']}")
        if result['invoked'] == 'Yes':
            for quote in result['quotes']:
                print(f"- Document Type: {quote['document_type']}")
                print(f"  Clause ID: {quote['clause']}")
                print(f"  Quote: {quote['quote']}")

    return {
        'company_name': company_name,
        'document_types': document_types,
        'po_analysis': po_analysis.model_dump(),  # Use model_dump instead of dict
        'clause_analysis': results
    }
