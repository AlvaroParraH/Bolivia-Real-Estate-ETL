# Airflow docker compose
Getting Airflow docker-compose.yaml from https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html
Create .env file
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
# Start DBT
uv run dbt init
# Change DBT files
/Users/alvaroparra/.dbt/profiles.yml
dbt_project.yml
# Add packages file and add dbt utils

# Rental analysis in Bolivia
This project is focus in extracting information from multiple sites, https://remax.bo/, https://c21.com.bo/, https://firmacasas.com/ that are websites dedicated to house/apartment rentals, To this analysis we are going to include facebook market as it is also a popular platform.

# Motivation
It is mostly based on my experience, I decided to rent a home in my hometown in Bolivia, I hired a company for it and they gave me price ranges bellow what I was expecting, they did they analysis for getting a rental price based on location and not the amenities of the apartment, they browse arround the websites, It took a week for the realtor to get the data and process it, I think that it was too slow and that the process took more than expected and it was unefficient and unnecesary.

# Next Steps
Expand into selling apartments, rental/selling homes and do it for main cities around Bolivia (La Paz/Cochabamba/Santa Cruz)

# Data Scrapping from websites
Data Scrapping would be done by using Spider and 
For facebook, We would need to use other tools

# Century 21 scraper
This project now includes a Playwright-based scraper for Century 21 Bolivia result pages.

Run it with:

```bash
.venv/bin/python main.py --limit 10 --format csv
.venv/bin/python main.py --limit 10 --output data/listings.json
.venv/bin/python main.py --limit 10 --output data/listings.csv --format csv
```

Outputs are now split by city and include a timestamp in the filename, for example:
`data/c21_house_listings_la-paz_20260703_143500.csv`.
Each run now writes files inside a datetime folder, for example:
`data/20260712_093000/c21_house_listings_la-paz_20260712_093000.csv`.
The default scrape targets the La Paz and Santa Cruz houses and houses-in-condominium sale results pages.

Current C21 behavior (temporary):
- The second phase (entering each listing detail page for map enrichment) is intentionally commented out in code.
- Only phase 1 (result/list page extraction) runs, which improves execution time.
- `map_google_url`, `map_latitude`, and `map_longitude` are currently exported as empty values (`null`).
- Each exported row includes `insert_datetime` (UTC ISO timestamp) to track ingestion time.

# RE/MAX scraper
This project now also includes a Playwright-based scraper for RE/MAX Bolivia search result pages.

Run it with:

```bash
.venv/bin/python main_remax.py --limit 10 --format csv
.venv/bin/python main_remax.py --limit 10 --output data/listings.json
.venv/bin/python main_remax.py --limit 10 --output data/listings.csv --format csv
```

Outputs are also split by city and include a timestamp in the filename, for example:
`data/remax_house_listings_la-paz_20260703_143500.csv`.
Each run now writes files inside a datetime folder, for example:
`data/20260712_093000/remax_house_listings_la-paz_20260712_093000.csv`.

# Firmacasas scraper
This project now also includes an API-based scraper for Firmacasas listings.

The default Firmacasas filters are:
- Categoria: Casa
- Tipo: Venta
- Ciudad: all cities

Run it with:

```bash
.venv/bin/python main_firmacasas.py --limit 10 --format csv
.venv/bin/python main_firmacasas.py --limit 10 --output data/listings.json
.venv/bin/python main_firmacasas.py --limit 10 --output data/listings.csv --format csv
.venv/bin/python main_firmacasas.py --city-id 1 --city-id 3 --limit 20 --format csv
```

Outputs are split by city and include a timestamp in the filename, for example:
`data/firmacasas_house_listings_la-paz_20260704_064113.csv`.
Each run now writes files inside a datetime folder, for example:
`data/20260712_093000/firmacasas_house_listings_la-paz_20260712_093000.csv`.

# Azure Blob upload behavior
By default, scraper runs only write files locally under `data/<YYYYMMDD_HHMMSS>/`.
Files are uploaded to Azure Blob Storage only when `--upload-azure` is explicitly provided.

Examples with `uv run`:

```bash
uv run main.py --format csv --upload-azure 
uv run main_remax.py --format csv --upload-azure
uv run main_firmacasas.py --format csv --upload-azure
```

Optional upload parameters (all three scripts):
- `--azure-container <container_name>`
- `--azure-prefix <blob/path/prefix>`

# Posting information on Reddit on Rentals
This information is going to be posted on reddit and comments are going to be monitored for improving it.

