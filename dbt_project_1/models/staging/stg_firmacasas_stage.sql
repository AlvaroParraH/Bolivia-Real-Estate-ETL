{{
    config(
        materialized='table',
        tags=['staging', 'firmacasas']
    )
}}

with staged as (
    select
        try_to_timestamp_tz(nullif(t.$1::string, '')) as insert_datetime,
        nullif(t.$2::string, '') as city,
        nullif(t.$3::string, '') as property_id,
        try_to_number(nullif(t.$4::string, '')) as listing_id,
        nullif(t.$5::string, '') as property_category,
        nullif(t.$6::string, '') as transaction_type,
        nullif(t.$7::string, '') as title,
        nullif(t.$8::string, '') as location,
        nullif(t.$9::string, '') as address,
        try_to_double(nullif(t.$10::string, '')) as land_m2,
        try_to_double(nullif(t.$11::string, '')) as construction_m2,
        try_to_number(nullif(t.$12::string, '')) as bedrooms,
        try_to_number(nullif(t.$13::string, '')) as bathrooms,
        try_to_number(nullif(t.$14::string, '')) as parking_spaces,
        nullif(t.$15::string, '') as price_text,
        try_to_double(nullif(t.$16::string, '')) as price_amount,
        nullif(t.$17::string, '') as currency,
        nullif(t.$18::string, '') as url,
        nullif(t.$19::string, '') as thumbnail_url,
        nullif(t.$20::string, '') as agent_name,
        nullif(t.$21::string, '') as agent_phone,
        metadata$filename::string as source_file,
        regexp_substr(metadata$filename::string, '(\\d{8}_\\d{6})', 1, 1, 'e', 1) as batch_timestamp,
        current_timestamp() as loaded_at
    from {{ var('firmacasas_stage_path', '@BOLIVIA_REAL_ESTATE.STAGE.BOLIVIA_REAL_ESTATE_STAGE/firmacasas/') }}
    (
        file_format => 'BOLIVIA_REAL_ESTATE.STAGE.SCRAPER_CSV_FF',
        pattern => '.*\\.csv'
    ) t
)

select *
from staged
