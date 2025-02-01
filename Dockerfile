# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only the requirements file first (to leverage Docker's caching for dependencies)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Set environment variables to ensure consistent output
ENV PYTHONUNBUFFERED=1

# Start the bot
CMD ["python", "main.py"]
