import os
from pypdf import PdfReader
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import config

# Initialize Google & Qdrant clients (Added 60-second timeout for Qdrant)
gemini_client = genai.Client(api_key=config.GOOGLE_API_KEY)
qdrant_client = QdrantClient(
    url=config.QDRANT_URL, 
    api_key=config.QDRANT_API_KEY,
    timeout=60.0
)

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Splits raw text into overlapping character chunks to preserve context at boundaries."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

def ensure_collection_exists():
    """Creates the Qdrant vector collection if it doesn't already exist."""
    collections = [c.name for c in qdrant_client.get_collections().collections]
    if config.COLLECTION_NAME not in collections:
        print(f"Creating Qdrant collection: '{config.COLLECTION_NAME}'...")
        qdrant_client.create_collection(
            collection_name=config.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=config.VECTOR_DIMENSION,
                distance=Distance.COSINE
            )
        )
        print("Collection created successfully!")

def process_and_index_pdfs(data_dir: str = "data"):
    """Reads all PDFs in data/, generates embeddings, and uploads to Qdrant Cloud in batches."""
    ensure_collection_exists()

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"Created '{data_dir}/' folder. Please place your PDF files inside it and re-run.")
        return

    pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDF files found in '{data_dir}/'. Please add at least one PDF file and re-run.")
        return

    points = []
    global_point_id = 1

    for pdf_name in pdf_files:
        pdf_path = os.path.join(data_dir, pdf_name)
        print(f"\nProcessing PDF: {pdf_name}...")
        reader = PdfReader(pdf_path)

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue

            chunks = chunk_text(page_text)
            for chunk in chunks:
                # 1. Generate 768-dimensional embedding vector
                response = gemini_client.models.embed_content(
                    model=config.EMBED_MODEL,
                    contents=chunk,
                    config=types.EmbedContentConfig(output_dimensionality=config.VECTOR_DIMENSION)
                )
                vector = response.embeddings[0].values

                # 2. Build payload metadata for citations
                payload = {
                    "text": chunk,
                    "source_file": pdf_name,
                    "page_number": page_num,
                    "type": "internal_pdf"
                }

                points.append(
                    PointStruct(
                        id=global_point_id,
                        vector=vector,
                        payload=payload
                    )
                )
                global_point_id += 1

    # Batch upsert points into Qdrant Cloud (20 vectors per request)
    if points:
        batch_size = 20
        print(f"\nUploading {len(points)} vector chunks to Qdrant Cloud in batches of {batch_size}...")
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            qdrant_client.upsert(
                collection_name=config.COLLECTION_NAME,
                points=batch
            )
            print(f"  -> Uploaded batch {i // batch_size + 1} ({len(batch)} chunks)")
        print("\nIngestion Complete! Your private knowledge base is ready.")

if __name__ == "__main__":
    process_and_index_pdfs()