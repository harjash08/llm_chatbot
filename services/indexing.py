import os
import tempfile
import zipfile
import requests
from urllib.parse import urlparse
from core.s3_config import s3_client, S3_BUCKET_NAME



MAX_ZIP_SIZE = 2 * 1024 * 1024 * 1024          # 2 GB
MAX_EXTRACTED_SIZE = 10 * 1024 * 1024 * 1024   # 10 GB
MAX_FILES = 20_000



ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".sql",
    ".xml",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".kt",
    ".swift",
}


IGNORED_DIRECTORIES = {
    # Git
    ".git",
    ".github",

    # Python environments
    ".venv",
    "venv",
    "env",
    "my_env",
    "myenv",

    # Python cache
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",

    # Vector databases
    "chroma_db",

    # JavaScript dependencies
    "node_modules",

    # Build and generated files
    "dist",
    "build",
    ".next",
    ".cache",
    "coverage",

    # Other generated data
    "site-packages",
}


def download_zip_from_s3(s3_key: str) -> str:
    """
    Download a ZIP file from AWS S3 to temporary storage.

    Returns:
        Path of the temporary ZIP file.
    """

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".zip"
    )

    temp_path = temp_file.name
    temp_file.close()

    try:
        response = s3_client.head_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )

        if response["ContentLength"] > MAX_ZIP_SIZE:
            raise ValueError(
                "ZIP file is larger than the allowed 2 GB."
            )

        s3_client.download_file(
            S3_BUCKET_NAME,
            s3_key,
            temp_path
        )

        return temp_path

    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)

        raise




def parse_github_url(repository_url: str):
    """
    Extract owner and repository name from a GitHub URL.
    """

    parsed = urlparse(repository_url)

    if parsed.netloc.lower() not in {
        "github.com",
        "www.github.com"
    }:
        raise ValueError(
            "Only GitHub repository URLs are supported."
        )

    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2:
        raise ValueError(
            "Invalid GitHub repository URL."
        )

    owner = parts[0]
    repo = parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo



def get_github_default_branch(owner: str, repo: str):
    """
    Get the default branch of a GitHub repository.
    """

    api_url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}"
    )

    response = requests.get(
        api_url,
        timeout=30
    )

    if response.status_code == 404:
        raise ValueError(
            "GitHub repository not found."
        )

    response.raise_for_status()

    data = response.json()

    return data["default_branch"]



def download_github_repository(repository_url: str) -> str:
    """
    Download a GitHub repository ZIP to a temporary file.

    Returns:
        Path of the temporary ZIP file.
    """

    owner, repo = parse_github_url(repository_url)

    branch = get_github_default_branch(
        owner,
        repo
    )

    zip_url = (
        f"https://github.com/{owner}/{repo}"
        f"/archive/refs/heads/{branch}.zip"
    )

    return download_zip_to_temp_file(zip_url)



def download_zip_to_temp_file(zip_url: str) -> str:
    """
    Download ZIP from a URL directly to disk.

    The complete ZIP is NOT loaded into RAM.
    """

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".zip"
    )

    temp_path = temp_file.name

    try:
        total_size = 0

        with requests.get(
            zip_url,
            stream=True,
            timeout=(30, 300)
        ) as response:

            response.raise_for_status()

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_length:
                content_length = int(content_length)

                if content_length > MAX_ZIP_SIZE:
                    raise ValueError(
                        "ZIP file is larger than the allowed 2 GB."
                    )

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if not chunk:
                    continue

                total_size += len(chunk)

                if total_size > MAX_ZIP_SIZE:
                    raise ValueError(
                        "ZIP file is larger than the allowed 2 GB."
                    )

                temp_file.write(chunk)

        temp_file.close()

        return temp_path

    except Exception:
        temp_file.close()

        if os.path.exists(temp_path):
            os.remove(temp_path)

        raise



def is_allowed_file(file_path: str) -> bool:
    """
    Check whether a file should be included in RAG indexing.
    """

    normalized_path = file_path.replace("\\", "/")
    parts = normalized_path.split("/")

    ignored_directories_lower = {
        directory.lower()
        for directory in IGNORED_DIRECTORIES
    }

    # Ignore files inside unwanted directories
    for part in parts[:-1]:
        if part.lower() in ignored_directories_lower:
            return False

    file_name = parts[-1].lower()

    # Ignore environment files and secrets
    if file_name == ".env" or file_name.startswith(".env."):
        return False

    # Ignore common generated and sensitive files
    if file_name in {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    }:
        return False

    # Check extension
    extension = os.path.splitext(file_name)[1].lower()

    return extension in ALLOWED_EXTENSIONS






def is_safe_zip_path(file_path: str) -> bool:
    """
    Prevent path traversal attacks such as:
        ../../malicious_file
    """

    normalized_path = os.path.normpath(
        file_path
    )

    if normalized_path.startswith(".."):
        return False

    if os.path.isabs(normalized_path):
        return False

    return True


def extract_zip_files(zip_path: str):
    """
    Read useful source files from a ZIP.

    The ZIP itself remains on disk.
    Individual source files are read into memory one at a time.
    """

    extracted_files = []

    total_extracted_size = 0

    with zipfile.ZipFile(zip_path, "r") as zip_file:

        members = zip_file.infolist()

        eligible_file_count = sum(
        1
        for member in members
        if not member.is_dir()
        and is_safe_zip_path(member.filename)
        and is_allowed_file(member.filename)
    )

        if eligible_file_count > MAX_FILES:
            raise ValueError(
                f"Repository contains too many indexable files. "
                f"Maximum allowed: {MAX_FILES}, "
                f"found: {eligible_file_count}."
            )

        for member in members:

            file_path = member.filename

            # Ignore directories
            if member.is_dir():
                continue

            # Security check
            if not is_safe_zip_path(file_path):
                raise ValueError(
                    f"Unsafe ZIP path detected: {file_path}"
                )

            
            if not is_allowed_file(file_path):
                continue

            
            total_extracted_size += member.file_size

            if total_extracted_size > MAX_EXTRACTED_SIZE:
                raise ValueError(
                    "Extracted repository is too large."
                )

            try:

                
                content = zip_file.read(member)

                text = content.decode(
                    "utf-8",
                    errors="ignore"
                )

            except Exception:
                continue

            extracted_files.append(
                {
                    "file_path": file_path,
                    "file_name": os.path.basename(
                        file_path
                    ),
                    "content": text,
                }
            )

    return extracted_files


def extract_project_source(
    source_type: str,
    repository_url: str | None = None,
    storage_path: str | None = None
):
    """
    Download and extract a project source.

    Supported sources:
        github
        upload
    """

    zip_path = None

    try:


        if source_type == "github":

            if not repository_url:
                raise ValueError(
                    "GitHub repository URL is required."
                )

            zip_path = download_github_repository(
                repository_url
            )

        

        elif source_type == "upload":

            if not storage_path:
                raise ValueError(
            "S3 storage path is required."
        )

            zip_path = download_zip_from_s3(storage_path)

     

        else:

            raise ValueError(
                "Invalid source type."
            )

    

        files = extract_zip_files(
            zip_path
        )

        return files

    finally:

       

        if zip_path and os.path.exists(zip_path):

            os.remove(zip_path)