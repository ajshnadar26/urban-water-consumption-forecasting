# Sources and data transformations

Retrieved on 14 October 2026. Water snapshots include January 2012–October 2025; analysis stops at December 2024 for the documented historical experiment.

| Source | Dataset | License |
|---|---|---|
| City of Austin | Austin Water Residential Water Consumption, sxk7-7k6z | Public Domain, source metadata |
| City of Austin | Austin Water Commercial Water Consumption, 5h9c-wmds | Public Domain, source metadata |
| Open-Meteo | Historical Weather API using ERA5 | CC BY 4.0, attribution required |

Exact endpoints used:

```text
https://data.austintexas.gov/resource/sxk7-7k6z.csv?$limit=100000
https://data.austintexas.gov/resource/5h9c-wmds.csv?$limit=100000
https://data.austintexas.gov/api/views/sxk7-7k6z.json
https://data.austintexas.gov/api/views/5h9c-wmds.json
https://archive-api.open-meteo.com/v1/archive?latitude=30.2672&longitude=-97.7431&start_date=2012-01-01&end_date=2025-12-31&daily=temperature_2m_mean,precipitation_sum&timezone=America%2FChicago&models=era5
```

The water API request limit exceeds both returned record counts. Dataset metadata is retained in `data/raw/`, with staff contacts and internal catalog details omitted from the public copy. Snapshot hashes and byte sizes are in `results/data_manifest.json`. Re-fetching the live sources can change the snapshot and results. Preserve the committed snapshot for exact reproduction.

Water fields: `year_month` (YYYYMM), `postal_code` (string), `customer_class` (billing category), `total_gallons` (US gallons in that billing month). Group by month and mapped sector, then divide gallons by 1,000,000. All four residential classes map to Residential. Commercial and Irrigation–Commercial map to Commercial; Large Volume and its irrigation category map to Large volume; City of Austin and its irrigation category map to Municipal. Utility and wholesale classes are excluded.

Weather fields: daily dates, mean 2m air temperature in °C, and precipitation sum in mm. Aggregate temperature by monthly mean and precipitation by monthly sum. The API data represents reanalysis at the Austin coordinate, not a utility weather-station observation. Calendar fields are derived deterministically from dates. No customer-level or personally identifying records are included.

Credit: City of Austin / Austin Water. Weather data by [Open-Meteo](https://open-meteo.com/), using ERA5; monthly aggregation is a transformation of the original daily data. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
