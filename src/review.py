import os
from dotenv import load_dotenv
from openai import OpenAI
import qdrant_client
from qdrant_client.models import VectorParams, Distance, PointStruct
import json
from langchain_text_splitters import MarkdownHeaderTextSplitter
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
    chunks = splitter.split_text(markdown_text)
    return chunks

pdf_path = "C:\\Users\\smckee\\Documents\\Test Contracts\\Incora\\Supplier-Quality-Flow-Down-Requirements-1.pdf"
tiff_path = "C:\\Users\\smckee\\Documents\\Test Contracts\\Incora\\Customer Contract_72250.tif"

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

def query_qdrant_for_clauses(client: QdrantClient, collection_name: str, query: str, top_k: int = 3) -> List[Dict]:
    query_vector = openai_client.embeddings.create(input=query, model=embedding_model_name).data[0].embedding
    search_result = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k
    )
    return [{"score": hit.score, "content": hit.payload["content"], "metadata": hit.payload["metadata"]} for hit in search_result]

# scan Tiff file which is the purchase order and use open ai to determine if there are specific clauses invoked from quality document or if there are any notable clauses
# params: po_markdown - markdown from the tiff file
def review_po(po_markdown):
    # put markdown into open ai and ask if there are specific clauses invoked from quality document
    response = openai_client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
            {"role": "user", "content": '''
             Analyse this purchase order carefully and determine the following:
             1. If there are specific clause identifiers for the quality document that are invoked in this purchase order.
                a) or if the entire quality document is invoked in this purchase order.
             2. If there are any requirements the make note of on the purchase order.

             Response Format (json):
             {
                "clause_identifiers": [list of clause identifiers],
                "requirements": [list of requirements]
             }

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
             ''' + po_markdown
             }
        ]
    )
    return response.choices[0].message.content

# determine the type of each document (po/tc/qc)
def determine_document_type(text: str) -> str:
    # Take the first 2000 characters of the text
    sample = text[:2000]

    # Prepare the prompt for OpenAI
    prompt = f"""
    Analyze the following text and determine if it is a Purchase Order, Quality Document, or Terms and Conditions.
    Respond with only one of these three options or "Unknown" if you can't determine.
    Response options: Purchase Order, Quality Document, Terms and Conditions, Unknown
    Only respond with that text and nothing else or else I will get an error
    
    Text sample:
    {sample}
    """

    # Call OpenAI for analysis
    response = openai_client.chat.completions.create(
        model="gpt-4o-2024-08-06",  # or your preferred model
        messages=[
            {"role": "system", "content": "You are an expert at identifying document types."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=10  # Limit the response to a short answer
    )

    # Extract the document type from the response
    document_type = response.choices[0].message.content.strip()

    # Validate the response
    valid_types = ["Purchase Order", "Quality Document", "Terms and Conditions", "Unknown"]
    return document_type if document_type in valid_types else "Unknown"

# Add this function to review documents
def review_documents(file_paths: List[str], company_name: str) -> Dict[str, Any]:
    # Initialize Qdrant client
    collection_name = f"{company_name}_documents"
    vector_size = 1536  # Size for text-embedding-3-small
    qdrant_client = initialize_qdrant(collection_name, vector_size)

    all_chunks = []
    all_embeddings = []
    document_types = {}
    po_analysis = None

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
            
            chunks = chunk_markdown_text(content)
            
            # Convert Document objects to dictionaries
            chunk_dicts = [{"page_content": chunk.page_content, "metadata": chunk.metadata} for chunk in chunks]
            
            embeddings = create_embeddings(chunk_dicts)
            
            all_chunks.extend(chunk_dicts)
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
        clause_results = query_qdrant_for_clauses(qdrant_client, collection_name, clause)
        
        # Prepare the prompt for OpenAI
        prompt = f"""
        Clause: {clause}
        Description: {description}
        
        Relevant text chunks:
        {json.dumps(clause_results, indent=2)}
        
        Based on the above information, is this clause invoked in the document? 
        Analyze the clause and return a JSON object with the following structure:
        {{
            "clause": "{clause}",
            "invoked": "Yes/No",
            "quotes": [
                {{"clause": "Clause ID", "quote": "Quote Text"}},
                {{"clause": "Clause ID", "quote": "Quote Text"}},
                ...
            ]
        }}
        
        Note: Only include quotes if the clause is invoked. If not invoked, return an empty list for quotes.
        """
        
        # Call OpenAI for analysis
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a legal expert analyzing contract clauses."},
                {"role": "user", "content": prompt}
            ]
        )
        
        analysis = json.loads(response.choices[0].message.content)
        
        # Append the analysis directly to the results list
        results.append(analysis)
    
    print("company name: ", company_name)
    print("document types: ", document_types)
    print("po analysis: ", po_analysis)
    print("clause analysis: ", results)

    return {
        'company_name': company_name,
        'document_types': document_types,
        'po_analysis': po_analysis,
        'clause_analysis': results
    }
