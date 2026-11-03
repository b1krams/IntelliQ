#!/usr/bin/env python3
"""Entrypoint for AWS Lambda Web Adapter (LWA) or direct execution."""
import os
import uvicorn
from lambdas.stream_worker.main import app

def handler(event, context):
    """Fallback handler if invoked as standard Lambda event."""
    return {"statusCode": 200, "body": "OK"}

if __name__ == "__main__":
    port = int(os.environ.get("AWS_LWA_PORT", "8080"))
    uvicorn.run("lambdas.stream_worker.main:app", host="0.0.0.0", port=port, workers=1)

