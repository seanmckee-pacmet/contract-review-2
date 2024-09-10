# bring in our LLAMA_CLOUD_API_KEY
from dotenv import load_dotenv
load_dotenv()

# bring in deps
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import os
import openai
import qdrant_client

openai_client = openai.Client(
    api_key=os.getenv("OPENAI_API_KEY")
)

client = qdrant_client.QdrantClient(":memory:")
collection_name = "test-collection"
embedding_model = "text-embedding-3-small"

# set up parser
parser = LlamaParse(
    result_type="markdown",  # "markdown" and "text" are available
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    model="gpt-4o-2024-08-06" 
)

# use SimpleDirectoryReader to parse our file
file_extractor = {".pdf": parser}
documents = SimpleDirectoryReader(input_files=['data/qc.pdf'], file_extractor=file_extractor).load_data()
text = ""
for page in documents:
    text += page.text

# Chunk the text by markdown symbol '#'
chunks = []
current_chunk = ""

for line in text.split('\n'):
    if line.strip().startswith('#'):
        if current_chunk:
            chunks.append(current_chunk.strip())
        current_chunk = line
    else:
        current_chunk += '\n' + line

# Add the last chunk if it's not empty
if current_chunk:
    chunks.append(current_chunk.strip())

def perform_search(query):
    search_results = client.search(
        collection_name=collection_name,
        query_vector=openai_client.embeddings.create(
            input=query,
            model=embedding_model
        ).data[0].embedding,
        limit=5
    )
    return search_results

# one extra dep
# from llama_index.core import VectorStoreIndex

# # create an index from the parsed markdown
# index = VectorStoreIndex.from_documents(documents)

# # create a query engine for the index
# query_engine = index.as_query_engine()

# # query the engine
# query = "Give me details for wqr23, wqr17, and anything about dfars. format in json"
# response = query_engine.query(query)
# print(response)

import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

# Load notable clauses from JSON file
with open('notable_clauses.json', 'r') as f:
    notable_clauses = json.load(f)

def check_document_for_clauses(file_path):
    # Read the document
    with open(file_path, 'r') as f:
        document_text = f.read()

    # Use OpenAI to analyze the document
    response = client.chat.completions.create(
        model="gpt-4",  # or another suitable model
        messages=[
            {"role": "system", "content": "You are a legal document analyzer. Identify notable clauses in the given text based on the provided descriptions."},
            {"role": "user", "content": f"Analyze the following document and identify any notable clauses based on these descriptions: {json.dumps(notable_clauses)}. Document text: {document_text}"}
        ]
    )

    # Parse the response and extract identified clauses
    identified_clauses = []
    for clause_type, description in notable_clauses.items():
        if clause_type.lower() in response.choices[0].message.content.lower():
            # Extract the relevant part of the text
            start_index = response.choices[0].message.content.lower().index(clause_type.lower())
            end_index = response.choices[0].message.content.find('\n', start_index)
            if end_index == -1:
                end_index = len(response.choices[0].message.content)
            clause_content = response.choices[0].message.content[start_index:end_index].strip()
            
            identified_clauses.append({
                "type": clause_type,
                "content": clause_content
            })

    return identified_clauses


