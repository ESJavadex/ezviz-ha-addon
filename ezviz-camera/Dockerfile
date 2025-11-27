ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.19
FROM $BUILD_FROM

# Install bashio, FFmpeg and Python dependencies
ARG BASHIO_VERSION="v0.16.2"
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    curl \
    jq \
    && mkdir -p /usr/src/bashio \
    && curl -L -f -s "https://github.com/hassio-addons/bashio/archive/${BASHIO_VERSION}.tar.gz" \
        | tar -xzf - --strip-components=1 -C /usr/src/bashio \
    && mv /usr/src/bashio/lib /usr/lib/bashio \
    && ln -s /usr/lib/bashio/bashio /usr/bin/bashio \
    && rm -rf /usr/src/bashio /var/cache/apk/*

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

# Make run script executable
RUN chmod a+x run.sh

# Run the application
CMD [ "/app/run.sh" ]
