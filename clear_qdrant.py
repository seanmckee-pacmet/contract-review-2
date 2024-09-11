import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

def clear_qdrant_database():
    # Initialize Qdrant client
    client = QdrantClient(
        url="https://50238ac6-e670-42be-933e-c836f812c16e.europe-west3-0.gcp.cloud.qdrant.io", 
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # Get all collections
    collections = client.get_collections().collections

    # Delete each collection
    for collection in collections:
        collection_name = collection.name
        print(f"Deleting collection: {collection_name}")
        client.delete_collection(collection_name=collection_name)

    print("All collections have been deleted. Your Qdrant database is now empty.")

if __name__ == "__main__":
    confirm = input("This will delete ALL collections in your Qdrant database. Are you sure? (yes/no): ")
    if confirm.lower() == 'yes':
        clear_qdrant_database()
    else:
        print("Operation cancelled.")