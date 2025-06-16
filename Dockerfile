FROM tiangolo/uwsgi-nginx-flask:python3.11

# Set working directory
WORKDIR /app

# Install ODBC Driver for SQL Server (matching your working setup)
RUN apt-get update && \
    apt-get install -y \
    curl \
    apt-transport-https \
    gnupg2 \
    lsb-release && \
    # Add Microsoft repository for Debian 11
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl -sSL https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    # Update package list
    apt-get update && \
    # Install ODBC packages (exactly what you have)
    ACCEPT_EULA=Y apt-get install -y \
    msodbcsql17 \
    unixodbc \
    unixodbc-dev && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the complete requirements file first for better layer caching
COPY requirements-full.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ /app/

# Set environment variables
ENV FLASK_APP=main.py
ENV PYTHONPATH=/app

# Create directories for caching
RUN mkdir -p /app/flask_cache && \
    chmod 755 /app/flask_cache

# The base image already handles uwsgi and nginx setup
# Expose ports
EXPOSE 80 443