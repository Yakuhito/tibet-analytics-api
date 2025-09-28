# Use the official Python base image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Create and activate a virtual environment
RUN python -m venv venv
RUN /bin/bash -c "source venv/bin/activate"

# Install requirements from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY *.py ./
COPY start.sh ./

# Expose the port the app will run on
EXPOSE 8000

# Set the start script as the entrypoint
ENTRYPOINT ["./start.sh"]
