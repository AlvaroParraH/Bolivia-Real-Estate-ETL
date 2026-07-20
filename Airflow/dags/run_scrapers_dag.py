from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

PROJECT_ROOT = "/opt/bolivia-real-estate-etl"
DEFAULT_ENV = {
    "PROJECT_ROOT": PROJECT_ROOT,
    "PYTHONUNBUFFERED": "1",
}

with DAG(
    dag_id="run_bolivia_real_estate_scrapers",
    description="Run the three Bolivia Real Estate scrapers sequentially",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        "owner": "airflow",
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["bolivia", "scrapers", "airflow"],
) as dag:
    prepare_playwright = BashOperator(
        task_id="prepare_playwright",
        bash_command="python -m playwright install chromium",
        env=DEFAULT_ENV,
    )

    run_c21 = BashOperator(
        task_id="run_c21_scraper",
        bash_command='cd "$PROJECT_ROOT" && python main.py --format csv --upload-azure',
        env=DEFAULT_ENV,
    )

    run_remax = BashOperator(
        task_id="run_remax_scraper",
        bash_command='cd "$PROJECT_ROOT" && python main_remax.py --format csv --upload-azure',
        env=DEFAULT_ENV,
    )

    run_firmacasas = BashOperator(
        task_id="run_firmacasas_scraper",
        bash_command='cd "$PROJECT_ROOT" && python main_firmacasas.py --format csv --upload-azure',
        env=DEFAULT_ENV,
    )

    prepare_playwright >> run_c21 >> run_remax >> run_firmacasas
