# rleb/Dockerfile
FROM python:3.11.2

# Set environment variables to avoid issues with locales
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

WORKDIR /app

# Copy project files
COPY . .

# postgressql c libraries
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Start the application
CMD ["python", "rleb_core.py"]
