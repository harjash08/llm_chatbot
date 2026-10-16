import asyncio
import os
import sys

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres import PostgresSaver

# Configure the Windows event loop before importing PGEngine.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

load_dotenv()

from core.vector_config import pg_engine_langchain
from router.auth import router
from router.project import project_router
from db.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing from the environment"
        )

    # Convert SQLAlchemy URL for LangGraph's checkpointer.
    if database_url.startswith("postgresql+psycopg://"):
        checkpointer_url = database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1
        )
    else:
        checkpointer_url = database_url

    # Initialize the vector table.
    await pg_engine_langchain.ainit_vectorstore_table(
        table_name="project_documents",
        vector_size=3072,
    )

    # Initialize LangGraph's PostgreSQL checkpointer.
    with PostgresSaver.from_conn_string(
        checkpointer_url
    ) as checkpointer:

        checkpointer.setup()

        app.state.checkpointer = checkpointer

        yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://llm-chatbot-frontend-oeqz.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(router)
app.include_router(project_router)