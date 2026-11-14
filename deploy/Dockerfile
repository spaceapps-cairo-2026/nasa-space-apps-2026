# Hugging Face Space (Docker). Built by Hugging Face from the folder `python run.py space stage` makes.
# One container runs the API and serves the app on port 7860, real data (MOCK=0).
FROM python:3.12-slim

# Hugging Face runs the container as user 1000; the trend engine writes NASA downloads into data/cache
# and world summaries into ml/outputs, so the app folder must belong to that user.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MOCK=0
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
