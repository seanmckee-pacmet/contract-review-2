import os
from dotenv import load_dotenv
from llama_parse import LlamaParse
from openai import OpenAI
import qdrant_client
from qdrant_client.models import VectorParams, Distance, PointStruct
import json

# Load environment variables
load_dotenv()

# Set up LlamaParse
parser = LlamaParse(
    result_type="markdown",
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    model="gpt-4o-2024-08-06"
)


