from langchain_postgres import PGEngine, PGVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI,GoogleGenerativeAIEmbeddings
import os
from sqlalchemy import text
from db.database import engine
from core.vector_config import pg_engine_langchain, embedding



from sqlalchemy import text
embedding = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001"
)


def get_file_chunks(project_id: int, file_name: str):
    query = text("""
        SELECT content, langchain_metadata
        FROM project_documents
        WHERE langchain_metadata->>'project_id' = :project_id
          AND langchain_metadata->>'file_name' = :file_name
        ORDER BY (langchain_metadata->>'chunk_index')::int
    """)

    with engine.connect() as connection:
        result = connection.execute(
            query,
            {
                "project_id": str(project_id),
                "file_name": file_name
            }
        )

        rows = result.fetchall()

    return rows





def get_retriever():
    vector_store = PGVectorStore.create_sync(
        engine=pg_engine_langchain,
        table_name="project_documents",
        embedding_service=embedding
    )

    retriever = vector_store.as_retriever(
        search_kwargs={"k": 3}
    )

    return retriever