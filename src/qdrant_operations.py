from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from qdrant_client import models

from src.document_processing import process_document
import os
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI
import tiktoken


openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
embedding_model_name = "text-embedding-3-small"

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
        except Exception as e:
            print(f"Failed to upload batch {i//batch_size + 1} after multiple retries: {str(e)}")

def query_qdrant_for_clauses(client: QdrantClient, collection_name: str, clause: str, description: str, top_k: int = 10) -> List[Dict]:
    query = f"{clause}: {description}"
    
    query_vector = openai_client.embeddings.create(input=query, model=embedding_model_name).data[0].embedding

    search_result = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k
    )
    return [
        {
            "content": hit.payload["content"], 
            "metadata": hit.payload["metadata"],
        } 
        for hit in search_result
    ]

def get_ai_response(client: QdrantClient, collection_name: str, query: str, max_tokens: int = 1000) -> str:
    # Embed the query
    query_vector = openai_client.embeddings.create(input=query, model=embedding_model_name).data[0].embedding

    # Search Qdrant for top 10 results
    search_result = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=10
    )

    # Prepare context from search results
    context = "\n\n".join([hit.payload["content"] for hit in search_result])

    # Prepare the prompt for OpenAI
    prompt = f"Context:\n{context}\n\nQuery: {query}\n\nAnswer:"


    # Get response from OpenAI
    response = openai_client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a helpful assistant who is an expert in contract law and aerospace engineering." 
             "Provide a concise answer to the query based on the given context. "
             "Please provide quotes from the context that support your answer only if absolutely necessary and make sure to shorten the quotes as much as possible."},
            {"role": "user", "content": prompt}
        ],
        # max_tokens=max_tokens,
        temperature=0,
    )

    return response.choices[0].message.content.strip()


def store_document_in_qdrant(client: QdrantClient, company_name: str, file_path: str):
    collection_name = company_name
    
    # Process the document
    _, doc_type, chunks, embeddings, _ = process_document(file_path)
    
    # Ensure the collection exists
    try:
        client.get_collection(collection_name)
    except:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=len(embeddings[0]), distance=models.Distance.COSINE)
        )
    
    # Store the document chunks
    client.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(
                id=str(i),
                vector=embedding,
                payload={
                    "text": chunk["page_content"],
                    "metadata": chunk["metadata"],
                    "document_name": os.path.basename(file_path),
                    "document_type": doc_type
                }
            ) for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
    )

def get_company_documents(client: QdrantClient, company_name: str) -> List[str]:
    collection_name = company_name
    
    try:
        # Fetch all points in the collection
        response = client.scroll(
            collection_name=collection_name,
            limit=10000,  # Adjust this value based on your expected maximum number of documents
            with_payload=True,
            with_vectors=False
        )
        
        # Extract unique document names
        document_names = set(point.payload.get("document_name") for point in response[0])
        return list(document_names)
    except Exception as e:
        print(f"Error fetching documents for {company_name}: {str(e)}")
        return []

def remove_document_from_qdrant(client: QdrantClient, company_name: str, document_name: str):
    collection_name = company_name
    
    try:
        # Find all points with the given document name
        response = client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False,
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_name",
                        match=models.MatchValue(value=document_name)
                    )
                ]
            )
        )
        
        # Extract the IDs of the points to remove
        point_ids = [point.id for point in response[0]]
        
        # Remove the points
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=point_ids)
        )
    except Exception as e:
        print(f"Error removing document {document_name} for {company_name}: {str(e)}")