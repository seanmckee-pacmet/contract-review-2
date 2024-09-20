from src.get_formatted_text import parse_document
from src.embeddings import create_embeddings
from src.utils import memoize
from typing import List, Dict
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from openai import OpenAI
import os
from src.po_analysis import review_po

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@memoize
def chunk_markdown_text(markdown_text):
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
        ("#####", "Header 5"),
        ("######", "Header 6")
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    initial_chunks = splitter.split_text(markdown_text)

    sub_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", ".", "!", "?", ";", ",", " ", ""]
    )

    final_chunks = []
    for chunk in initial_chunks:
        header = next((chunk.metadata[key] for key in chunk.metadata if key.startswith("Header")), "")
        if len(chunk.page_content) > 1000:
            sub_chunks = sub_splitter.split_text(chunk.page_content)
            for sub_chunk in sub_chunks:
                final_chunks.append({
                    "page_content": sub_chunk,
                    "metadata": {"header": header}
                })
        else:
            final_chunks.append({
                "page_content": chunk.page_content,
                "metadata": {"header": header}
            })

    return final_chunks

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
        ]
    )

    return response.choices[0].message.content.strip()

def process_document(file_path):
    content = parse_document(file_path)

    doc_type = determine_document_type(content)

    chunks = chunk_markdown_text(content)
    
    # Extract just the file name without extension
    document_name = file_path.split('/')[-1].split('.')[0]
    
    for chunk in chunks:
        chunk['metadata']['document_type'] = doc_type
        chunk['metadata']['document_name'] = document_name
    
    embeddings = create_embeddings(chunks)
    
    po_analysis = None
    if doc_type == "Purchase Order":
        po_analysis = review_po(content)
    
    return file_path, doc_type, chunks, embeddings, po_analysis