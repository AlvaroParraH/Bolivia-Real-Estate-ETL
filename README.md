# Airflow docker compose
Getting Airflow docker-compose.yaml from https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html
# Create .env file
# Run docker compose
docker compose up -d
# Access to airflow
Go to http://localhost:8080/auth/login/
User/Password: airflow
# Start airflow
docker compose up airflow-init
# Stop airflow
docker compose down
# Start uv and install packages
uv init
uv add dbt-core dbt-snowflake
# To uninstall
uv remove dbt-core dbt-snowflake
# uv commands
uv tree
uv sync
uv pip list
# To check installed 
uv run dbt --version
