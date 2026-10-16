import asyncio
import os
import sys
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from langgraph.checkpoint.postgres import PostgresSaver

# Configure the Windows event loop before importing modules

# that initialize PGEngine.

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
    asyncio.WindowsSelectorEventLoopPolicy()
    )

load_dotenv()

from router.auth import router
from router.project import project_router
from db.database import Base, engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.getenv("DATABASE_URL")


    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing from the .env file"
        )

# Convert the SQLAlchemy URL to a native PostgreSQL URL
# for LangGraph's Psycopg-based checkpointer.
    if database_url.startswith("postgresql+psycopg://"):
        checkpointer_url = database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1
        )
    else:
        checkpointer_url = database_url

# Keep the checkpointer open while FastAPI is running.
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
"http://127.0.0.1:5173",
],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)
Base.metadata.create_all(bind=engine)

app.include_router(router)
app.include_router(project_router)
