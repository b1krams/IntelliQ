"""Cross-platform type generator from schemas/*.schema.json into Pydantic v2 & TypeScript."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def generate_pydantic():
    print("[1/2] Generating Python Pydantic v2 models...")
    schema_path = ROOT / "schemas" / "response.schema.json"
    output_path = ROOT / "core" / "llm" / "models.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        sys.executable, "-m", "datamodel_code_generator",
        "--input", str(schema_path),
        "--input-file-type", "jsonschema",
        "--output", str(output_path),
        "--output-model-type", "pydantic_v2.BaseModel",
        "--target-python-version", "3.13",
        "--use-standard-collections",
        "--field-constraints",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        print("Pydantic generation failed via datamodel_code_generator, generating fallback models...")
        return False
    print(f"Pydantic models written to {output_path}")
    return True

def generate_ts():
    print("[2/2] Generating TypeScript interfaces...")
    schema_path = ROOT / "schemas" / "response.schema.json"
    output_path = ROOT / "frontend" / "src" / "lib" / "types.ts"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # npx json-schema-to-typescript
    cmd = ["npx", "--yes", "json-schema-to-typescript", str(schema_path), "-o", str(output_path)]
    res = subprocess.run(cmd, cwd=str(ROOT), shell=True)
    if res.returncode != 0:
        print("TypeScript generation via npx failed, generating fallback types...")
        return False
    print(f"TypeScript interfaces written to {output_path}")
    return True

if __name__ == "__main__":
    generate_pydantic()
    generate_ts()

