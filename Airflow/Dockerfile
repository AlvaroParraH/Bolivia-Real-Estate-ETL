FROM apache/airflow:3.1.7

USER root

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN mkdir -p /ms-playwright \
    && chown -R airflow:0 /ms-playwright

USER airflow

RUN pip install --no-cache-dir \
    playwright \
    azure-storage-blob \
    pandas \
    dbt-core \
    dbt-snowflake

USER root

RUN PYTHONPATH=/home/airflow/.local/lib/python3.12/site-packages \
    python -m playwright install --with-deps chromium \
    && chown -R airflow:0 /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

USER airflow
