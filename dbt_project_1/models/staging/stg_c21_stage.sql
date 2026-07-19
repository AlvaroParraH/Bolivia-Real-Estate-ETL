{{
    config(
        materialized='table',
        tags=['staging', 'c21']
    )
}}

with staged as (
    select
        try_to_timestamp_tz(nullif(t.$1::string, '')) as insert_datetime,
        nullif(t.$2::string, '') as city,
        nullif(t.$3::string, '') as property_id,
        nullif(t.$4::string, '') as property_type,
        nullif(t.$5::string, '') as title,
        nullif(t.$6::string, '') as location,
        try_to_number(nullif(t.$7::string, '')) as land_m2,
        try_to_number(nullif(t.$8::string, '')) as construction_m2,
        try_to_number(nullif(t.$9::string, '')) as bedrooms,
        try_to_number(nullif(t.$10::string, '')) as bathrooms,
        try_to_number(nullif(t.$11::string, '')) as parking_spaces,
        nullif(t.$12::string, '') as price_text,
        try_to_number(nullif(t.$13::string, '')) as price_amount,
        nullif(t.$14::string, '') as url,
        nullif(t.$15::string, '') as thumbnail_url,
        nullif(t.$16::string, '') as map_google_url,
        try_to_double(nullif(t.$17::string, '')) as map_latitude,
        try_to_double(nullif(t.$18::string, '')) as map_longitude,
        metadata$filename::string as source_file,
        regexp_substr(metadata$filename::string, '(\\d{8}_\\d{6})', 1, 1, 'e', 1) as batch_timestamp,
        current_timestamp() as loaded_at
    from {{ var('c21_stage_path', '@BOLIVIA_REAL_ESTATE.STAGE.BOLIVIA_REAL_ESTATE_STAGE/c21/') }}
    (
        file_format => 'BOLIVIA_REAL_ESTATE.STAGE.SCRAPER_CSV_FF',
        pattern => '.*\\.csv'
    ) t
)

select *
from staged
