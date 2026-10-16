import os
import sys
import asyncio

from dotenv import load_dotenv
from langchain_postgres import PGEngine
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables

load_dotenv()

# Configure the Windows event loop for Psycopg

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
    asyncio.WindowsSelectorEventLoopPolicy()
    )

# Get PostgreSQL database URL

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from the .env file")

# Create LangChain PostgreSQL engine

pg_engine_langchain = PGEngine.from_connection_string(
url=DATABASE_URL
)

# Initialize embedding model

embedding = GoogleGenerativeAIEmbeddings(
model="gemini-embedding-001"
)
