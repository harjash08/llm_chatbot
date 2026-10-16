from fastapi import APIRouter,Depends,UploadFile, File,Request,Form,BackgroundTasks
from schemas.user import *
from db.database import get_db
from sqlalchemy.orm import Session
from db.models import *
from fastapi import APIRouter,Depends,HTTPException,Request,BackgroundTasks
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt
from schemas.project_schema import *
from core.helper import is_authenticated
import cloudinary.uploader
import core.s3_config
from services.indexing import extract_project_source
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI,GoogleGenerativeAIEmbeddings
from langchain_postgres import PGEngine, PGVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import AnyMessage,AIMessage,HumanMessage
from core.settings import settings
import os
import re
from dotenv import load_dotenv
import asyncio
from core.s3_config import s3_client, S3_BUCKET_NAME
from boto3.s3.transfer import TransferConfig
from services.project_indexer import index_project
from core.retriver import *
from langchain_core.documents import Document
from fastapi.responses import StreamingResponse
import json
from typing import TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from core.vector_config import pg_engine_langchain, embedding
from fastapi import Request
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )
load_dotenv()

project_router=APIRouter()

llm = ChatGoogleGenerativeAI(
     model="gemini-3.8-flash",
     temperature=0
       )
embedding = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001"
)



class ChatState(TypedDict):
    messages: list[AnyMessage]
    documents: list[Document]
    summary:str

# pg_engine.init_vectorstore_table(
#     table_name="project_documents",
#     vector_size=3072
# )

@project_router.post("/create_project/",response_model=ProjectResponse)
def create_project(body:CreateProject,current_user:UserModel=Depends(is_authenticated), db:Session=Depends(get_db)):
    existing_project = db.query(Project).filter(
    Project.name == body.name,
    Project.user_id == current_user.id
).first()
    if  existing_project:
            raise HTTPException(
                status_code=403,
                detail="Project name already exist."
        )
    project=Project(
             user_id=current_user.id,
             name=body.name,
             description=body.description

        )
    db.add(project)
    db.commit()
    db.refresh(project)

    return project

@project_router.get("/projects/", response_model=list[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(is_authenticated),
):
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .all()
    )

    return projects

@project_router.post(
    "/project_source/",
    response_model=ProjectSourceResponse
)
def project_source(
    project_id: int,
    repository_url: str | None = None,
    storage_path: UploadFile | None = File(None),
    current_user: UserModel = Depends(is_authenticated),
    db: Session = Depends(get_db)
):



    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

   

    if bool(repository_url) == bool(storage_path):
        raise HTTPException(
            status_code=400,
            detail="Provide either repository_url or storage_path"
        )

   

    if repository_url:

      

        source_type = "github"
        repository = repository_url
        s3_key = None

   

    else:

        if not storage_path.filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=400,
                detail="Only ZIP files are allowed"
            )

        source_type = "upload"
        repository = None

     

        import uuid

        safe_filename = (
            f"{uuid.uuid4().hex}_{storage_path.filename}"
        )

        s3_key = (
            f"ai-codebase-assistant/projects/"
            f"{project_id}/{safe_filename}"
        )

        config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=16 * 1024 * 1024,
            max_concurrency=2,
            use_threads=True
        )


        try:

            s3_client.upload_fileobj(
                storage_path.file,
                S3_BUCKET_NAME,
                s3_key,
                ExtraArgs={
                    "ContentType": "application/zip"
                },
                Config=config
            )

        except Exception as e:

            raise HTTPException(
                status_code=500,
                detail=f"AWS S3 upload failed: {str(e)}"
            )

        finally:
            storage_path.file.close()

  

    source = Project_Source(
        project_id=project_id,
        source_type=source_type,
        repository_url=repository,
        storage_path=s3_key
    )

    try:

        db.add(source)
        db.commit()
        db.refresh(source)

    except Exception:

        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save project source"
        )

 

    try:

        index_project(
            project_id=project_id,
            source_type=source.source_type,
            repository_url=source.repository_url,
            storage_path=source.storage_path
        )

    except Exception as e:

  

        raise HTTPException(
            status_code=500,
            detail=f"Project indexing failed: {str(e)}"
        )

 

    return source


@project_router.post("/conversation/{project_id}/",response_model=ConversationResponse)
def create_conversation(project_id: int,current_user:UserModel=Depends(is_authenticated),db:Session=Depends(get_db)):

    project=db.query(Project).filter(
        Project.id==project_id,
        Project.user_id==current_user.id).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    conversation = Conversation(
    project_id=project_id,
    user_id=current_user.id,
    title=None
)

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation

@project_router.get(
"/conversation/{project_id}/",
response_model=list[ConversationResponse]
)
def get_conversation(
project_id: int,
current_user: UserModel = Depends(is_authenticated),
db: Session = Depends(get_db)
):

    project = db.query(Project).filter(
    Project.id == project_id,
    Project.user_id == current_user.id
    ).first()


    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    conversations = db.query(Conversation).filter(
        Conversation.project_id == project_id,
        Conversation.user_id == current_user.id
    ).order_by(Conversation.id.desc()).all()

    return conversations



@project_router.post("/chat/{conversation_id}/")
def create_message(
    conversation_id: int,
    body: CreateMessage,
    request: Request,
    current_user: UserModel = Depends(is_authenticated),
    db: Session = Depends(get_db)
):
    print("========== CHAT ENDPOINT HIT ==========", flush=True)
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        print("Conversation not found")
        raise HTTPException(
            status_code=404,
            detail="Conversation not found" )
        

    user_message = body.message

    if conversation.title is None or conversation.title == "New Conversation":
        conversation.title = user_message
        db.commit()
        db.refresh(conversation)

    chat = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        message=user_message
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

 

    def retreival_node(state:ChatState):
        print("========== RETRIEVAL NODE STARTED ==========", flush=True)
        user_message = state["messages"][-1].content
        match = re.search(
        r"\b[\w.-]+\."
        r"(?:py|js|jsx|ts|tsx|java|cpp|c|h|hpp|cs|php|go|rs|rb|swift|kt|html|css|sql|json|xml|yaml|yml|sh|ipynb)\b",
        user_message,
        re.IGNORECASE
    )


        file_name = match.group(0) if match else None

    
        if file_name:
            rows = get_file_chunks(
                project_id=conversation.project_id,
                file_name=file_name
            )

            result = [
                Document(
                    page_content=row[0],
                    metadata=row[1] or {}
                )
                for row in rows
            ]

        else:
            retriever = get_retriever()
            result = retriever.invoke(user_message)

    
        return {"documents":result}



    system_prompt = """
        You are a helpful and intelligent codebase assistant.

        Answer the user's question naturally, clearly, and directly.

        Instructions:
        1. Explain code in your own words instead of copying chunks.
        2. Use the relevant code to answer questions about specific files.
        3. Combine information from multiple files when necessary.
        4. Give filenames and file paths when available.
        5. Do not invent information that is not supported by the code.
        6. If the available context is insufficient, explain what is missing.
        7. Start with a direct answer and avoid unnecessary introductions.
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        (
            "human",
            """
            Previous conversation:
            {summary}

            Relevant code from the project:
            {content}

            Current user question:
            {question}

            Answer the current question using the relevant code.
            """
        )
    ])
   

    def history(state: ChatState):

        previous_messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.id < chat.id
            )
            .order_by(ChatMessage.id.asc())
            .all()
        )

        if not previous_messages:
            return {"summary": ""}

        conversation_text = "\n".join(
            f"{message.role}: {message.message}"
            for message in previous_messages
        )

        return {
            "summary": conversation_text
        }


    def generate_answer(state: ChatState):
        try:
            documents = state.get("documents", [])

            
            content = "\n\n".join(
                f"""
                File name: {doc.metadata.get('file_name', 'Unknown')}
                File path: {doc.metadata.get('file_path', 'Unknown')}

                Code:
                {doc.page_content}
                """
                for doc in documents
            )

            user_message = state["messages"][-1].content

            summary = state.get("summary", "")

            prompt_result = prompt.invoke({
                "content": content if content.strip() else "No relevant documents found.",
                "question": user_message,
                "summary": summary
            })

            messages = prompt_result.to_messages()

            if not any(
                isinstance(message, HumanMessage)
                for message in messages
            ):
                raise ValueError(
                    "Prompt must contain a HumanMessage with the user question."
                )

            print("PROMPT MESSAGE COUNT:", len(messages), flush=True)
            print("USER QUESTION:", user_message, flush=True)

            response = llm.invoke(messages)

            answer = response.content

            if isinstance(answer, list):
                answer = "".join(
                    block.get("text", "")
                    for block in answer
                    if isinstance(block, dict)
                    and block.get("type") == "text"
                )

            print("ANSWER GENERATED SUCCESSFULLY", flush=True)

            return {
                "messages": [
                    AIMessage(content=answer)
                ]
            }

        except Exception as e:
            import traceback

            print(
                "ERROR INSIDE generate_answer:",
                repr(e),
                flush=True
            )
            traceback.print_exc()
            raise



        

    graph=StateGraph(ChatState)


    graph.add_node("retreival_node",retreival_node) 
    graph.add_node("history",history)
    graph.add_node("generate_answer",generate_answer) 

    graph.add_edge(START,"retreival_node")
    graph.add_edge("retreival_node","history")
    graph.add_edge("history","generate_answer")
    graph.add_edge("generate_answer",END)

    checkpointer = request.app.state.checkpointer

    
    DB_URI = os.getenv("DATABASE_URL")



    app_graph = graph.compile(checkpointer=checkpointer)

    config = {
        "configurable": {
            "thread_id": str(conversation_id)
        }
    }

    def generate_response():
        full_answer = ""
        print("========== STARTING LANGGRAPH EXECUTION ==========", flush=True)
        try:
            for message_chunk, metadata in app_graph.stream(
                {
                    "messages": [HumanMessage(content=user_message)],
                    "documents": [],
                    "summary": ""
                },
                config=config,
                stream_mode="messages"
            ):
              
                if metadata.get("langgraph_node") != "generate_answer":
                    continue

                text_chunk = message_chunk.content

                if isinstance(text_chunk, str) and text_chunk:
                    full_answer += text_chunk

                    yield (
                        f"data: {json.dumps({'chunk': text_chunk})}\n\n"
                    )

            ai_chat = ChatMessage(
                conversation_id=conversation_id,
                role="ai",
                message=full_answer
            )

            db.add(ai_chat)
            db.commit()
            db.refresh(ai_chat)

            yield (
                "event: done\n"
                f"data: {json.dumps({'id': ai_chat.id, 'conversation_id': conversation_id, 'role': 'ai'})}\n\n"
            )

        
        except Exception as e:
            import traceback
            import sys

            print(
                "\n========== ERROR DURING RESPONSE GENERATION ==========",
                file=sys.stderr,
                flush=True
            )

            print(
                f"Exception type: {type(e).__name__}",
                file=sys.stderr,
                flush=True
            )

            print(
                f"Exception message: {repr(e)}",
                file=sys.stderr,
                flush=True
            )

            traceback.print_exc(file=sys.stderr)

            db.rollback()

            yield (
                "event: error\n"
                f"data: {json.dumps({'error': str(e)})}\n\n"
            )



        finally:
            db.close()

    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@project_router.post("/conversation/{project_id}/",response_model=ConversationResponse)
def create_conversation(project_id: int,current_user:UserModel=Depends(is_authenticated),db:Session=Depends(get_db)):

    project=db.query(Project).filter(
        Project.id==project_id,
        Project.user_id==current_user.id).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    conversation = Conversation(
    project_id=project_id,
    user_id=current_user.id,
    title=None
)

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation

@project_router.get("/chat_conversation/{conversation_id}/",response_model=list[MessageResponse])
def get_chat(conversation_id: int,current_user:UserModel=Depends(is_authenticated),db:Session=Depends(get_db)):

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    chat = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.id.asc()).all()

    return chat