from openai import OpenAI
from typing import List, Dict
import time
import os
from src.utils import memoize

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
embedding_model_name = "text-embedding-3-small"

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
            
            
            time.sleep(1)
        except Exception as e:
            print(f"Error processing batch {i//batch_size + 1}: {str(e)}")
    
    return all_embeddings