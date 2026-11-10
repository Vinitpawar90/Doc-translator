
import os
import time
import tempfile
import requests

from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException
)

from fastapi.responses import Response
#from fastapi import FastAPI
from .database import engine, Base, get_db
from .models import APIKey, TranslationHistory
from .auth import validate_api_key

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Document Translation API",
    description="Document translation with usage monitoring",
    version="2.0.0"
)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

DEEPL_API_URL = os.getenv(
    "DEEPL_API_URL",
    "https://api-free.deepl.com"
).rstrip("/")

if not DEEPL_API_KEY:
    raise RuntimeError("DEEPL_API_KEY is missing")


@app.get("/")
def home():
    return {
        "message": "Document Translation API is running",
        "version": "2.0.0"
    }


@app.post("/translate")
def translate_document(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form(None),

    db: Session = Depends(get_db),

    api_key: APIKey = Depends(validate_api_key)
):

    allowed_extensions = {
        ".pdf", ".docx", ".pptx",
        ".xlsx", ".txt", ".html", ".srt"
    }

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is missing"
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported document format"
        )

    if not target_lang.strip():
        raise HTTPException(
            status_code=400,
            detail="Target language is required"
        )

    start_time = time.time()
    history = None

    headers = {
        "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"
    }

    try:

        with tempfile.TemporaryDirectory() as temp_dir:

            input_path = Path(temp_dir) / f"input{extension}"

            # Save uploaded document with a size limit
            file_size = 0
            max_file_size = 20 * 1024 * 1024

            with open(input_path, "wb") as output:

                while True:

                    chunk = file.file.read(1024 * 1024)

                    if not chunk:
                        break

                    file_size += len(chunk)

                    if file_size > max_file_size:
                        raise HTTPException(
                            status_code=413,
                            detail="Maximum upload size is 20 MB"
                        )

                    output.write(chunk)

            # Create translation history
            history = TranslationHistory(
                api_key_id=api_key.id,
                filename=Path(file.filename).name,
                document_type=extension.replace(".", "").upper(),
                source_language=source_lang,
                target_language=target_lang.upper(),
                file_size=file_size,
                status="Pending"
            )

            db.add(history)
            db.commit()
            db.refresh(history)

            # STEP 1: Upload document to DeepL
            upload_data = {
                "target_lang": target_lang.strip().upper()
            }

            if source_lang and source_lang.strip():
                upload_data["source_lang"] = source_lang.strip().upper()

            with open(input_path, "rb") as document:

                response = requests.post(
                    f"{DEEPL_API_URL}/v2/document",
                    headers=headers,
                    data=upload_data,
                    files={
                        "file": (
                            input_path.name,
                            document
                        )
                    },
                    timeout=120
                )

            response.raise_for_status()

            result = response.json()

            document_id = result["document_id"]
            document_key = result["document_key"]

            status_data = {
                "document_key": document_key
            }

            # STEP 2: Check document status
            for attempt in range(120):

                status_response = requests.post(
                    f"{DEEPL_API_URL}/v2/document/{document_id}",
                    headers=headers,
                    data=status_data,
                    timeout=30
                )

                status_response.raise_for_status()

                status = status_response.json()

                print("Translation status:", status["status"])

                if status["status"] == "done":
                    break

                if status["status"] == "error":

                    raise HTTPException(
                        status_code=502,
                        detail=status.get(
                            "error_message",
                            "DeepL translation failed"
                        )
                    )

                time.sleep(2)

            else:

                raise HTTPException(
                    status_code=504,
                    detail="Translation timed out"
                )

            # STEP 3: Download translated document
            download_response = requests.post(
                f"{DEEPL_API_URL}/v2/document/{document_id}/result",
                headers=headers,
                data=status_data,
                timeout=120
            )

            download_response.raise_for_status()

            translated_content = download_response.content

            # Save translated document permanently
            safe_filename = f"translated_{Path(file.filename).name}"
            output_path = OUTPUT_DIR / safe_filename
            with open(output_path, "wb") as f:
                f.write(translated_content)
            
            # STEP 4: Update successful translation history
            history.status = "Success"

            history.duration_seconds = round(
                time.time() - start_time, 2
            )

            db.commit()

            return Response(
                content=translated_content,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition":
                    f'attachment; filename="{safe_filename}"'
                }
            )

    except HTTPException as e:

        if history is not None:
            history.status = "Failed"
            history.error_message = str(e.detail)[:500]
            history.duration_seconds = round(
                time.time() - start_time, 2
            )
            db.commit()

        raise

    except requests.RequestException as e:

        print("DEEPL ERROR:", str(e))

        if e.response is not None:
            print("DEEPL STATUS:", e.response.status_code)
            print("DEEPL RESPONSE:", e.response.text)

        if history is not None:
            history.status = "Failed"
            history.error_message = (
                "DeepL request failed"
            )
            history.duration_seconds = round(
                time.time() - start_time, 2
            )
            db.commit()

        raise HTTPException(
            status_code=502,
            detail="DeepL API request failed"
        )

    except Exception as e:

        print("SERVER ERROR:", repr(e))

        if history is not None:
            history.status = "Failed"
            history.error_message = "Internal server error"
            history.duration_seconds = round(
                time.time() - start_time, 2
            )
            db.commit()

        raise HTTPException(
            status_code=500,
            detail="Internal translation server error"
        )


# Health check
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }




OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)