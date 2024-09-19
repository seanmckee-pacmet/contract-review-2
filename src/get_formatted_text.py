from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import os
from dotenv import load_dotenv
from PIL import Image
import pytesseract
import traceback

load_dotenv()

# Set up LlamaParse
parser = LlamaParse(
    result_type="markdown",
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    model="gpt-4o-2024-08-06"
)

def parse_pdf_to_markdown(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file {pdf_path} does not exist.")
    
    try:
        file_extractor = {".pdf": parser}
        reader = SimpleDirectoryReader(input_files=[pdf_path], file_extractor=file_extractor)
        
        documents = reader.load_data()

        
        if documents:
            markdown_content = []
            for doc in documents:
                if hasattr(doc, 'text'):
                    markdown_content.append(doc.text)
                elif hasattr(doc, 'page_content'):
                    markdown_content.append(doc.page_content)
                else:
                    print(f"Warning: Document doesn't have 'text' or 'page_content' attribute: {doc}")
            return "\n\n".join(markdown_content)
        else:
            print(f"No documents were parsed from {pdf_path}")
            return ""
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()
        return ""

def parse_tiff_to_markdown(tiff_path):
    if not os.path.exists(tiff_path):
        raise FileNotFoundError(f"The file {tiff_path} does not exist.")
    
    pytesseract.pytesseract.tesseract_cmd = 'C:\\Users\\smckee\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe'
    
    full_text = ""
    with Image.open(tiff_path) as img:
        for i in range(img.n_frames):
            img.seek(i)
            text = pytesseract.image_to_string(img)
            full_text += f"Page {i+1}:\n{text}\n\n"
    
    # Use LlamaParse to convert the OCR text to markdown
    file_extractor = {".txt": parser}
    with open("temp.txt", "w", encoding="utf-8") as temp_file:
        temp_file.write(full_text)
    documents = SimpleDirectoryReader(input_files=["temp.txt"], file_extractor=file_extractor).load_data()
    os.remove("temp.txt")
    
    if documents:
        return "\n\n".join(doc.text for doc in documents)
    return ""

def parse_document(doc_path):
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"The file {doc_path} does not exist.")
    
    if doc_path.lower().endswith(".pdf"):
        return parse_pdf_to_markdown(doc_path)
    elif doc_path.lower().endswith((".tiff", ".tif")):
        return parse_tiff_to_markdown(doc_path)
    else:
        raise ValueError(f"Unsupported file type: {doc_path}")

def get_formatted_text(file_path):
    response = parse_document(file_path)
    return response