FROM python:3.11-slim

# Set working directory
WORKDIR /workspace

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    procps \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Verify Node.js and npm installation
RUN node --version && npm --version

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install UV (Python package installer) - optional for future use
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:$PATH"

# Install Google Generative AI SDK for Gemini
RUN pip install --no-cache-dir google-generativeai

# Install MCP with CLI tools
RUN pip install --no-cache-dir "mcp[cli]"

# Clone and setup Splunk MCP Server (using livehybrid/splunk-mcp - actively maintained)
RUN git clone https://github.com/livehybrid/splunk-mcp.git /opt/splunk-mcp && \
    cd /opt/splunk-mcp && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install

# Add Splunk MCP server to PATH
ENV PATH="/opt/splunk-mcp:$PATH"

# Expose Jupyter port
EXPOSE 8888

# Create notebooks directory
RUN mkdir -p /workspace/notebooks

# Set up Jupyter configuration
RUN jupyter notebook --generate-config && \
    echo "c.NotebookApp.token = ''" >> ~/.jupyter/jupyter_notebook_config.py && \
    echo "c.NotebookApp.password = ''" >> ~/.jupyter/jupyter_notebook_config.py

# Default command
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--notebook-dir=/workspace/notebooks"]