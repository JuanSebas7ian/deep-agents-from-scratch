FROM python:3.11-slim
WORKDIR /app

# Install deps
COPY src/supervisor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Global Assets
COPY skills/ /app/skills/

# Copy Shared Lib (Monorepo)
COPY src/shared/ /app/src/shared/
COPY src/__init__.py /app/src/

# Copy Supervisor Code
COPY src/supervisor/ /app/src/supervisor/

# Run Worker
CMD ["python", "-m", "src.supervisor.worker"]
