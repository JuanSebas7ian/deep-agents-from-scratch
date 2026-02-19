FROM python:3.12-slim
WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create package structure mappings
WORKDIR /app/neuro_agent
COPY domain/ /app/neuro_agent/domain/
COPY infrastructure/ /app/neuro_agent/infrastructure/
COPY apps/supervisor/ /app/neuro_agent/apps/supervisor/

# Initialize empty package init
RUN touch /app/neuro_agent/__init__.py

# Ensure Python discovers the fully qualified imports
ENV PYTHONPATH=/app

# Run Worker
CMD ["python", "-m", "neuro_agent.apps.supervisor.worker"]
