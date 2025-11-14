# Python 3.11 image
FROM python:3.11-slim

# Working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files
COPY . .

# Run bot
CMD ["python", "taxi_bot_final.py"]
