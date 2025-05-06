# Use Python 3.10 as base image since it's compatible with the dependencies
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user for security
RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

# Command to run the bot
CMD ["python", "src/main.py"] 