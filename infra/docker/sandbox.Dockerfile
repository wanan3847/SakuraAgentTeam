# Docker sandbox image for SakuraAgentTeam
# This image provides a safe execution environment for agent tools

FROM python:3.11-slim

# Install common development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages commonly used in development
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pytest \
    ruff \
    pyright

# Create non-root user for security
RUN useradd -m -s /bin/bash agent

# Set up working directory
WORKDIR /workspace

# Set permissions
RUN chown -R agent:agent /workspace

# Switch to non-root user
USER agent

# Default command
CMD ["/bin/bash"]
