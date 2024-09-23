from src.document_processing import process_document
from src.po_analysis import review_po
from src.clause_analysis import analyze_clauses_batch
from src.qdrant_operations import initialize_qdrant, store_embeddings_in_qdrant, query_qdrant_for_clauses
from src.utils import load_notable_clauses
import concurrent.futures
import asyncio
from typing import List, Dict, Any
import json
import os
from openai import OpenAI

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def review_documents(file_paths: List[str], company_name: str, selected_documents: List[str]) -> Dict[str, Any]:
    print(f"Clause Analysis for {company_name}\n")

    print(f"[DEBUG] Starting review for company: {company_name}")
    print(f"[DEBUG] Files to process: {file_paths}")

    collection_name = f"{company_name}"
    vector_size = 1536  # Size for text-embedding-3-small
    qdrant_client = initialize_qdrant(collection_name, vector_size)
    print(f"[DEBUG] Initialized Qdrant collection: {collection_name}")

    all_chunks = []
    all_embeddings = []
    document_types = {}
    po_analysis = None
    invoked_clauses = []
    all_invoked = False

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_document, file_path) for file_path in file_paths]
        for future in concurrent.futures.as_completed(futures):
            try:
                file_path, doc_type, chunks, embeddings, doc_po_analysis = future.result()
                document_types[file_path] = doc_type
                all_chunks.extend(chunks)
                all_embeddings.extend(embeddings)
                
                if doc_type == "Purchase Order" and doc_po_analysis:
                    po_analysis = doc_po_analysis
                    all_invoked = po_analysis.all_invoked
                    invoked_clauses = po_analysis.clause_identifiers
                
                print(f"[DEBUG] Processed {file_path}: {len(chunks)} chunks created, doc_type: {doc_type}")
                if doc_po_analysis:
                    print(f"[DEBUG] PO Analysis for {file_path}: all_invoked={all_invoked}, invoked_clauses={invoked_clauses}")
            except Exception as e:
                print(f"[DEBUG] Error processing {file_path}: {str(e)}")

    print(f"[DEBUG] Total chunks: {len(all_chunks)}, Total embeddings: {len(all_embeddings)}")
    store_embeddings_in_qdrant(qdrant_client, collection_name, all_chunks, all_embeddings)
    print(f"[DEBUG] Stored embeddings in Qdrant collection: {collection_name}")

    notable_clauses = load_notable_clauses()
    print(f"[DEBUG] Loaded notable clauses structure")

    results = []
    prompts = []

    for clause_id, clause_info in notable_clauses.items():
        print(f"\nAnalyzing clause: {clause_id}")
        print(f"Description: {clause_info['Description']}")
        
        clause_results = query_qdrant_for_clauses(qdrant_client, collection_name, clause_id, clause_info['Description'])
        print(f"DEBUG: Clause results: {clause_results}")

        print(f"Found {len(clause_results)} relevant text chunks for clause: {clause_id}")
        
        prompt = f"""
        Given the following information:

        Clause ID: {clause_id}
        Description: {clause_info['Description']}
        

        Relevant text chunks:
        {json.dumps(clause_results, indent=2)}

        Purchase Order Analysis:
        po_invokes_all_clauses: {all_invoked}
        invoked_clauses: {json.dumps(invoked_clauses)}

        General Instructions:
        - based off all the quotes provided, determine if the clause is invoked and which quotes invoke it
        - use instructions below as a guide to determine if the clause is invoked and to select the most relevant quotes

        Background Information:
        These quotes come from documents supplied by a buyer.
        We are the seller/vendor/supplier.
        If the quote mandates that a seller/vendor/supplier must comply, then the quote is relevant and invoked as long as it passes the following task criteria:

        Task:
        1. Determine if the clause is invoked based on the following criteria:
        a. Analyze each text chunk for relevance to the clause and its description.

        Here are some examples of quotes that invoke the clause (assuming PO invokes it):
        {json.dumps(clause_info['Examples'], indent=2)}
        b. Consider a clause invoked if ANY of the following conditions are met:
            - The chunk mentions or implies the clause's application
            - The chunk describes a situation, requirement, or mandate that aligns with the clause's intent
            - The chunk states a general requirement for compliance with the clause (e.g., terms like "must comply with DFARS," "subject to FAR regulations," or "in accordance with XYZ standards")
            - For **Terms and Conditions** or **compliance-related documents**, any mention of compliance, regulations, or standards relevant to the clause should be considered an invocation
            - For **Quality Documents**:
                * If po_invokes_all_clauses is true, consider the clause invoked
                * If po_invokes_all_clauses is false, only consider the clause invoked if it's in the invoked_clauses list
                    - This is very important. You cannot include a quote from a clause that is not in the invoked_clauses list if po_invokes_all_clauses is false.
        c. For non-Quality Documents, evaluate each chunk independently for clause invocation.

        2. If the clause is determined to be invoked, select the MOST relevant quote that:
        - Directly and unambiguously relates to the clause or its description
        - Provides the clearest evidence for the clause's application (such as compliance mandates or regulatory references)
        - Extract only the most relevant portion of the quote, while ensuring sufficient context is maintained
        - Additional quotes are allowed at your discretion.

        3. Format your response as a JSON object with the following structure:
        {{
            "clause": "{clause_id}",
            "invoked": "Yes" or "No",
            "quotes": [
                {{
                    "quote": "Concise, relevant excerpt from the text",
                    "document_type": "Type of document containing the quote",
                    "header": "Header of the document containing the quote",
                    "requires_human_review": "Yes" or "No"  // Change this line
                }},
                // Include a second quote ONLY if absolutely necessary
            ]
        }}

        Important notes:
        - Only include the "quotes" field if the clause is invoked.
        - Be highly selective in choosing quotes. Prioritize quality and relevance over quantity.
        - Extract only the most relevant parts of quotes, but include enough context for clarity.
        - Use ellipsis (...) to indicate omitted text at the beginning or end of a quote if necessary.
        - Ensure compliance-related mandates from documents like **Terms and Conditions** or other regulatory references are treated as clause invocations.

        Please analyze the given information thoroughly and provide your response in the specified JSON format, ensuring a focused evaluation of clause invocation with minimal, highly relevant, and concise quotes, including whether each quote requires human review.
        """
        
        prompts.append(prompt)

    print(f"Sending {len(prompts)} prompts to OpenAI for clause analysis in batches")
    
    # Create a new event loop and run the coroutine
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    analyses = loop.run_until_complete(analyze_clauses_batch(openai_client, prompts))
    loop.close()
    
    for analysis in analyses:
        if analysis and analysis.invoked == 'Yes':
            results.append(analysis.model_dump())
            print(f"Clause {analysis.clause} is invoked. Added to results.")
        elif analysis:
            print(f"Clause {analysis.clause} is not invoked. Skipped.")
        else:
            print("Failed to analyze a clause")

    print(f"Review completed. Total results: {len(results)}")

   

    return {
        "company_name": company_name,
        "po_analysis": po_analysis.model_dump() if po_analysis else None,
        "clause_analysis": results
    }