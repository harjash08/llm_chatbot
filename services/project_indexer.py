from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from langchain_postgres import PGVectorStore

from core.vector_config import pg_engine_langchain, embedding

from services.indexing import extract_project_source


def index_project(
    project_id: int,
    source_type: str,
    repository_url: str | None = None,
    storage_path: str | None = None
):

    # 1. Extract project files

    files = extract_project_source(
        source_type=source_type,
        repository_url=repository_url,
        storage_path=storage_path
    )

    # 2. Initialize the text splitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    documents = []

    # 3. Split every extracted file into chunks

    for file in files:

        content = file.get("content", "")

        if not content.strip():
            continue

        chunks = splitter.split_text(content)

        for index, chunk in enumerate(chunks):

            document = Document(
                page_content=chunk,
                metadata={
                    "project_id": project_id,
                    "file_path": file["file_path"],
                    "file_name": file["file_name"],
                    "file_type": file.get(
                        "file_type",
                        ""
                    ),
                    "chunk_index": index
                }
            )

            documents.append(document)

    # 4. Stop if no content was extracted

    if not documents:
        raise ValueError(
            "No supported source code was found to index"
        )

    # 5. Connect to the existing vector store

    vector_store = PGVectorStore.create_sync(
        engine=pg_engine_langchain,
        table_name="project_documents",
        embedding_service=embedding
    )

    # 6. Generate embeddings and save documents

    vector_store.add_documents(documents)

    return {
        "project_id": project_id,
        "indexed_chunks": len(documents),
        "message": "Project indexed successfully"
    }