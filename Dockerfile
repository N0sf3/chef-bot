# Dockerfile — the recipe for the container Coolify will build and run.
# A container is a sealed box with exactly what the bot needs, nothing else.

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (this layer caches, so rebuilds are fast).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot's code in.
COPY . .

# The DB lives here; Coolify will mount a persistent volume at /data so the
# palate memory survives redeploys.
ENV DB_PATH=/data/chef.db

# Start the bot.
CMD ["python", "bot.py"]
