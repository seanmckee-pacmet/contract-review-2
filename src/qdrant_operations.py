from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import os
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

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
            print(f"Uploaded batch {i//batch_size + 1} of {(len(points)-1)//batch_size + 1}")
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
