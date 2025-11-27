ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.19
FROM $BUILD_FROM

# Install FFmpeg and Python dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    dos2unix \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Create virtual environment and install Python packages
ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ezviz_stream.py .
COPY stream_to_pipe.py .
COPY run.sh .

# Fix line endings and make run script executable
RUN dos2unix run.sh && chmod a+x run.sh

# Run the application
CMD [ "/app/run.sh" ]
