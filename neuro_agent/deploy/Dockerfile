FROM python:3.11-slim

WORKDIR /app

COPY deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and skills
COPY src/ /app/src/
COPY skills/ /app/skills/
COPY main.py /app/main.py

# Specify the command to run your App Runner server (e.g., using FastAPI or simple execution)
# CMD ["python", "main.py"]
