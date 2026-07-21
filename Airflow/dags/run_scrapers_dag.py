from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

PROJECT_ROOT = "/opt/bolivia-real-estate-etl"
DEFAULT_ENV = {
    "PROJECT_ROOT": PROJECT_ROOT,
    "PYTHONUNBUFFERED": "1",
    "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
    "UV_CACHE_DIR": "/home/airflow/.cache/uv",
}


def _scraper_command(script_name: str) -> str:
    return f"""
cd "$PROJECT_ROOT"
upload_flag=""
if [[ -n "${{AZURE_STORAGE_CONNECTION_STRING:-}}" || -n "${{AZURE_STORAGE_CONTAINER_SAS_URL:-}}" || ( -n "${{AZURE_STORAGE_ACCOUNT_URL:-}}" && -n "${{AZURE_STORAGE_SAS_TOKEN:-}}" ) ]]; then
    upload_flag=" --upload-azure"
fi
python {script_name} --format csv${{upload_flag}}
""".strip()


def _dbt_command(select_model: str) -> str:
    return f"""
cd "$PROJECT_ROOT"
profiles_dir="${{DBT_PROFILES_DIR:-/home/airflow/.dbt}}"
if [[ ! -f "$profiles_dir/profiles.yml" ]]; then
    echo "Skipping dbt model {select_model}: profiles.yml not found at $profiles_dir"
    exit 0
fi
dbt run --project-dir dbt_project_1 --profiles-dir "$profiles_dir" --select {select_model}
""".strip()


def _dbt_deps_command() -> str:
    return """
cd "$PROJECT_ROOT"
profiles_dir="${DBT_PROFILES_DIR:-/home/airflow/.dbt}"
if [[ ! -f "$profiles_dir/profiles.yml" ]]; then
    echo "Skipping dbt deps: profiles.yml not found at $profiles_dir"
    exit 0
fi
dbt deps --project-dir dbt_project_1 --profiles-dir "$profiles_dir"
""".strip()

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
    scrape_c21 = BashOperator(
        task_id="scrape_c21",
        bash_command=_scraper_command("main.py"),
        env=DEFAULT_ENV,
        append_env=True,
    )

    scrape_remax = BashOperator(
        task_id="scrape_remax",
        bash_command=_scraper_command("main_remax.py"),
        env=DEFAULT_ENV,
        append_env=True,
    )

    scrape_firmacasas = BashOperator(
        task_id="scrape_firmacasas",
        bash_command=_scraper_command("main_firmacasas.py"),
        env=DEFAULT_ENV,
        append_env=True,
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=_dbt_deps_command(),
        env=DEFAULT_ENV,
        append_env=True,
    )

    dbt_stg_c21 = BashOperator(
        task_id="dbt_stg_c21",
        bash_command=_dbt_command("stg_c21_stage"),
        env=DEFAULT_ENV,
        append_env=True,
    )

    dbt_stg_remax = BashOperator(
        task_id="dbt_stg_remax",
        bash_command=_dbt_command("stg_remax_stage"),
        env=DEFAULT_ENV,
        append_env=True,
    )

    dbt_stg_firmacasas = BashOperator(
        task_id="dbt_stg_firmacasas",
        bash_command=_dbt_command("stg_firmacasas_stage"),
        env=DEFAULT_ENV,
        append_env=True,
    )

    scrape_c21 >> scrape_remax >> scrape_firmacasas >> dbt_deps >> dbt_stg_c21 >> dbt_stg_remax >> dbt_stg_firmacasas
