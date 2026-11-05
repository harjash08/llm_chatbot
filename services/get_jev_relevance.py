import os
import requests
from dotenv import load_dotenv

load_dotenv()

def evaluate_relevance(question, documents):

    url = "https://opencode.ai/zen/v1/systemone"

    headers = {
        "Authorization": f"Bearer {os.getenv('JEV_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "jev-1.13-free",

        "state": {
            "question": question,
            "documents": documents
        },

        "questions": {
            "context_sufficient": {
                "type": "noul",
                "instructions": (
                    "Does the provided context contain "
                    "enough relevant information to answer "
                    "the question accurately?"
                )
            }
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    return result["answers"]["context_sufficient"]["noul"]