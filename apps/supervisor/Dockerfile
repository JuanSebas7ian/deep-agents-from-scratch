FROM python:3.12-slim
WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create package structure mappings
COPY src/ /app/src/
COPY apps/ /app/apps/
COPY pyproject.toml /app/

RUN pip install -e .

# Ensure Python discovers the fully qualified imports
ENV PYTHONPATH=/app

# Run Worker
CMD ["python", "-m", "apps.supervisor.worker"]
