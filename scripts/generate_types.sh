#!/usr/bin/env bash
set -e

echo "=== Generating Pydantic v2 Models from JSON Schema ==="
uv run datamodel-codegen \
  --input schemas/response.schema.json \
  --input-file-type jsonschema \
  --output core/llm/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.13 \
  --use-standard-collections \
  --field-constraints

echo "=== Generating TypeScript Interfaces from JSON Schema ==="
npx json-schema-to-typescript schemas/response.schema.json -o frontend/src/lib/types.ts

echo "=== Type Generation Complete ==="

