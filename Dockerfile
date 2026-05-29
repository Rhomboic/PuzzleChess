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

# MODEL and API keys are injected at runtime via ECS — never baked in
ENTRYPOINT ["python", "main.py"]
