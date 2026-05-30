FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY agent/ agent/
COPY data/ data/
COPY eval/ eval/
COPY main.py .

# results/ dir for local writes before S3 upload
RUN mkdir -p results

# MODEL is baked into the image at build time — API keys injected at runtime
ARG MODEL
ENV MODEL=$MODEL

ENTRYPOINT ["python", "main.py"]
