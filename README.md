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

By default, CSV files are written to `data/c21_listings.csv` inside the project.
The default scrape targets the La Paz and Santa Cruz houses and houses-in-condominium sale results pages.

# Posting information on Reddit on Rentals
This information is going to be posted on reddit and comments are going to be monitored for improving it.

