FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Build tools are needed for any package without a prebuilt wheel.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Rebuild the corpus and retrain the classifier inside the image so the
# persisted joblib artefacts always match the scikit-learn/numpy versions
# installed above. A training failure then breaks the build, not a request.
RUN python ml_model/build_dataset.py && python ml_model/train_model.py

EXPOSE 8000

# The database is created and seeded by the FastAPI lifespan handler on start.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
