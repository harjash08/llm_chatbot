from langchain_postgres import PGEngine, PGVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI,GoogleGenerativeAIEmbeddings
import os
from sqlalchemy import text
from db.database import engine
from core.vector_config import pg_engine_langchain, embedding
from langchain_classic.retrievers import BM25Retriever
from langchain_core.documents import Document
from sqlalchemy import text

embedding = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001"
)



def get_file_chunks(project_id: int, file_name: str | None = None):

    if file_name is not None:
        query = text("""
            SELECT content, langchain_metadata
            FROM project_documents
            WHERE langchain_metadata->>'project_id' = :project_id
              AND langchain_metadata->>'file_name' = :file_name
            ORDER BY (langchain_metadata->>'chunk_index')::int
        """)

        params = {
            "project_id": str(project_id),
            "file_name": file_name
        }

    else:
        query = text("""
            SELECT content, langchain_metadata
            FROM project_documents
            WHERE langchain_metadata->>'project_id' = :project_id
            ORDER BY
                langchain_metadata->>'file_path',
                (langchain_metadata->>'chunk_index')::int
        """)

        params = {
            "project_id": str(project_id)
        }

    with engine.connect() as connection:
        result = connection.execute(query, params)
        rows = result.fetchall()

    return rows





def get_retriever(project_id:int):
    vector_store = PGVectorStore.create_sync(
        engine=pg_engine_langchain,
        table_name="project_documents",
        embedding_service=embedding
    )

    retriever = vector_store.as_retriever(
        search_kwargs={"k": 3,"filter":{"project_id":project_id}}
    )
    

    return retriever





def get_sparse_retriever(project_id: int):

    # Fetch indexed chunks for this project from PostgreSQL.
    rows = get_file_chunks(project_id=project_id)

    documents = [
        Document(
            page_content=row["content"],
            metadata=row["metadata"] or {}
        )
        for row in rows
    ]

    sparse_retriever = BM25Retriever.from_documents(
        documents,
        k=10
    )

    return sparse_retriever