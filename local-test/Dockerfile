FROM python:3.11-slim

# Install ffmpeg and dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir requests pycryptodome

# Create working directories
RUN mkdir -p /app /hls

WORKDIR /app

# Copy all app files (copied by build script)
COPY ezviz_stream.py /app/
COPY stream_to_pipe.py /app/
COPY run_local.sh /app/

RUN chmod +x /app/run_local.sh

EXPOSE 8080

CMD ["/app/run_local.sh"]
