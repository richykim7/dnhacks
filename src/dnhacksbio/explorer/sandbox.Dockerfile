# Explorer sandbox image: an open-source scientific and comp-bio Python stack the explorer's code runs in.
# Everything here is permissively licensed (BSD/MIT/Apache/LGPL). Datasets are not baked in; they are
# mounted read-only at /data at run time. Extend by adding to the pip line (open-source only).
FROM python:3.11-slim

# build tools for any packages that compile; removed after to keep the image lean
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy pandas scipy statsmodels scikit-learn \
    pyarrow duckdb \
    biopython \
    gseapy \
    pingouin \
    matplotlib \
    openpyxl \
    GEOparse anndata h5py       # robust GEO download+parse + single-cell .h5ad loading

# non-root default; at run time we also pass --user <host-uid>:<host-gid> so outputs are host-owned
RUN useradd -m -u 10001 sci
USER sci
WORKDIR /work
