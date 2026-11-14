"""Hugging Face Space entry point for the free Gradio SDK (Hugging Face runs `python app.py`).

Gradio itself is not used: this starts the CropShift Earth API and app on port 7860, on real data.
The Docker SDK does the same through deploy/Dockerfile.
"""
import os

import uvicorn

os.environ.setdefault("MOCK", "0")

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
