ARG BUILD_FROM
FROM $BUILD_FROM

# Install FFmpeg and Python dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY ezviz_stream.py .
COPY stream_to_pipe.py .
COPY run.sh .

# Make run script executable
RUN chmod a+x run.sh

# Run the application
CMD [ "/app/run.sh" ]
