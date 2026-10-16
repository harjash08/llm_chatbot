import boto3
import os

from dotenv import load_dotenv
from botocore.config import Config
from boto3.s3.transfer import TransferConfig

load_dotenv()

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
    config=Config(
        connect_timeout=30,
        read_timeout=300,
        retries={
            "max_attempts": 5,
            "mode": "standard"
        },
        max_pool_connections=20
    )
)

S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

S3_TRANSFER_CONFIG = TransferConfig(
    multipart_threshold=8 * 1024 * 1024,
    multipart_chunksize=16 * 1024 * 1024,
    max_concurrency=2,
    use_threads=True
)

