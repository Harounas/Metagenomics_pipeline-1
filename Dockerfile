# Use a base image with Python 3.8
FROM python:3.8-slim

# Install Miniconda
RUN apt-get update && apt-get install -y \
    wget \
    bzip2 \
    && wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda \
    && rm Miniconda3-latest-Linux-x86_64.sh \
    && /opt/conda/bin/conda clean -tipsy

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
