FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Build tools are needed for any package without a prebuilt wheel.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies as root, into the system site-packages.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Run as a non-root user with UID 1000.
#
# This is not just good practice: Hugging Face Spaces runs every container as
# UID 1000, so anything owned by root is read-only at runtime. DigiSafe writes
# its SQLite database, uploaded evidence files, and generated PDF reports into
# the application directory, so those must be owned by this user or the app
# cannot store a single piece of evidence.
RUN useradd --create-home --uid 1000 appuser
USER appuser
ENV HOME=/home/appuser
ENV PATH=/home/appuser/.local/bin:$PATH

WORKDIR /home/appuser/app
COPY --chown=appuser:appuser . /home/appuser/app

# No training step: the models are committed and requirements.txt pins the
# exact scikit-learn/numpy/scipy versions that produced them, so the pickles
# load as-is. Retrain with ml_model/train_model.py if the corpus changes.

EXPOSE 8000

# Shell form so ${PORT} is expanded at runtime. Hosts that inject a port
# (Railway, Fly, Cloud Run) are honoured; Hugging Face Spaces and plain
# `docker run` fall back to 8000, which is what app_port in README.md declares.
# The database is created and seeded by the FastAPI lifespan handler on start.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
