#!/bin/sh
exec python -m uvicorn lambdas.stream_worker.main:app --host 0.0.0.0 --port 8080 --workers 1

