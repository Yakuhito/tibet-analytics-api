# Use the official Python base image
FROM python:3.9

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY *.py ./
COPY start.sh ./

# Expose the port the app will run on
EXPOSE 8000

# Set the start script as the entrypoint
ENTRYPOINT ["./start.sh"]
