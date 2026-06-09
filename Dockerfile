FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN mkdir -p src/synth_data_creator && touch src/synth_data_creator/__init__.py
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .
COPY main.py ./

# Create output directory
RUN mkdir -p /output

CMD ["python", "-m", "synth_data_creator.main"]
