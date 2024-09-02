# Use an Ubuntu base image with Python 3.8
FROM ubuntu:20.04

# Set environment variables to avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    bzip2 \
    ca-certificates \
    && wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda \
    && rm Miniconda3-latest-Linux-x86_64.sh \
    && /opt/conda/bin/conda clean --all --yes \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PATH=/opt/conda/bin:$PATH
ENV CONDA_ENV_PATH=/opt/conda/envs/newenv

# Create and activate the Conda environment
COPY environment.yml .
RUN conda env create -f environment.yml

# Install pip dependencies (if any)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Set the working directory
WORKDIR /app

# Copy the rest of the application code
COPY . .

# Set the entry point for the container
ENTRYPOINT ["conda", "run", "--name", "newenv", "python", "kraken_and_abundanceplots.py"]
