import os
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI
import tiktoken
from supabase import create_client, Client
import dotenv
import numpy as np

dotenv.load_dotenv()

# Initialize OpenAI client and set embedding model
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
embedding_model_name = "text-embedding-3-small"

def initialize_supabase() -> Client:
    """
    Initialize and return a Supabase client.
    """
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return supabase

def setup_vector_table(supabase: Client, table_name: str):
    """
    Set up a table with a vector column for storing document embeddings.
    If the table doesn't exist, it creates one.
    """
    # Check if the table exists, if not create it
    result = supabase.table(table_name).select("id").limit(1).execute()
    if result.data == []:
        # Create the table with vector column
        supabase.sql(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                content TEXT,
                metadata JSONB,
                embedding vector(1536)
            );
        """).execute()

def create_match_documents_function(supabase: Client):
    """
    Create a PostgreSQL function for vector similarity search.
    This function should be run once to set up the necessary database function.
    """
    supabase.sql("""
    CREATE OR REPLACE FUNCTION match_documents(query_embedding vector(1536), match_threshold float, match_count int, table_name text)
    RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        similarity float
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY EXECUTE format('
            SELECT id, content, metadata, 1 - (embedding <=> $1) AS similarity
            FROM %I
            WHERE 1 - (embedding <=> $1) > $2
            ORDER BY similarity DESC
            LIMIT $3
        ', table_name)
        USING query_embedding, match_threshold, match_count;
    END;
    $$;
    """).execute()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def upsert_with_retry(supabase: Client, table_name: str, batch: List[Dict]):
    """
    Upsert a batch of documents into the specified table with retry logic.
    """
    try:
        supabase.table(table_name).upsert(batch).execute()
    except Exception as e:
        print(f"Error during upsert: {str(e)}")
        raise

def store_embeddings(supabase: Client, table_name: str, chunks: List[Dict], embeddings: List[List[float]]):
    """
    Store document chunks and their embeddings in the specified table.
    """
    points = [
        {
            "content": chunk["page_content"],
            "metadata": chunk["metadata"],
            "embedding": embedding
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]
    
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]
        try:
            upsert_with_retry(supabase, table_name, batch)
        except Exception as e:
            print(f"Failed to upload batch {i//batch_size + 1} after multiple retries: {str(e)}")

def query_similar_documents(supabase: Client, table_name: str, query: str, top_k: int = 10) -> List[Dict]:
    """
    Query for documents similar to the given query string.
    """
    query_vector = openai_client.embeddings.create(input=query, model=embedding_model_name).data[0].embedding

    result = supabase.rpc(
        'match_documents',
        {
            'query_embedding': query_vector,
            'match_threshold': 0.5,
            'match_count': top_k,
            'table_name': table_name
        }
    ).execute()

    return [
        {
            "content": item['content'],
            "metadata": item['metadata']
        }
        for item in result.data
    ]

def get_ai_response(supabase: Client, table_name: str, query: str, max_tokens: int = 1000) -> str:
    """
    Get an AI-generated response based on similar documents to the query.
    """
    similar_docs = query_similar_documents(supabase, table_name, query, top_k=10)
    context = "\n\n".join([doc['content'] for doc in similar_docs])

    prompt = f"Context:\n{context}\n\nQuery: {query}\n\nAnswer:"

    response = openai_client.chat.completions.create(
        model="gpt-4-0314",
        messages=[
            {"role": "system", "content": "You are a helpful assistant who is an expert in contract law and aerospace engineering. "
             "Provide a concise answer to the query based on the given context. "
             "Please provide quotes from the context that support your answer only if absolutely necessary and make sure to shorten the quotes as much as possible."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0,
    )

    return response.choices[0].message.content.strip()

def store_document(supabase: Client, company_name: str, file_path: str):
    """
    Process a document and store its chunks and embeddings in Supabase.
    """
    table_name = f"{company_name}_documents"
    
    _, doc_type, chunks, embeddings, _ = process_document(file_path)
    
    setup_vector_table(supabase, table_name)
    
    for chunk, embedding in zip(chunks, embeddings):
        chunk["metadata"]["document_name"] = os.path.basename(file_path)
        chunk["metadata"]["document_type"] = doc_type
    
    store_embeddings(supabase, table_name, chunks, embeddings)

def get_company_documents(supabase: Client, company_name: str) -> List[str]:
    """
    Retrieve a list of document names for a given company.
    """
    table_name = f"{company_name}_documents"
    
    try:
        result = supabase.table(table_name).select('metadata->document_name').execute()
        document_names = set(item['metadata']['document_name'] for item in result.data)
        return list(document_names)
    except Exception as e:
        print(f"Error fetching documents for {company_name}: {str(e)}")
        return []

def remove_document(supabase: Client, company_name: str, document_name: str):
    """
    Remove a specific document from the company's document table.
    """
    table_name = f"{company_name}_documents"
    
    try:
        supabase.table(table_name).delete().eq('metadata->>document_name', document_name).execute()
    except Exception as e:
        print(f"Error removing document {document_name} for {company_name}: {str(e)}")

# Main setup function
def setup_supabase_vector_search(supabase: Client):
    """
    Set up the necessary database functions for vector search.
    This should be run once when setting up the project.
    """
    create_match_documents_function(supabase)