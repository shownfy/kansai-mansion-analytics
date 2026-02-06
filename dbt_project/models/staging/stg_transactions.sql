{{ config(materialized='view') }}

-- ステージング: 生データのクレンジングと標準化
with source as (
    select * from {{ source('raw', 'transaction_data') }}
    where "Type" like '%マンション%'
),

cleaned as (
    select
        -- 識別子
        row_number() over () as transaction_id,

        -- 物件情報
        "Prefecture" as prefecture,
        "Municipality" as municipality,
        "DistrictName" as district_name,
        "FloorPlan" as floor_plan_raw,
        "Structure" as structure_raw,

        -- 数値情報（空文字・NULLを処理）
        try_cast(nullif("TradePrice", '') as bigint) as trade_price,
        try_cast(nullif("Area", '') as numeric) as area_sqm,
        try_cast(nullif("CoverageRatio", '') as numeric) as coverage_ratio,
        try_cast(nullif("FloorAreaRatio", '') as numeric) as floor_area_ratio,

        -- 建築年の正規化
        "BuildingYear" as building_year_raw,
        case
            when "BuildingYear" like '令和%' then
                2018 + cast(regexp_extract("BuildingYear", '令和(\d+)年', 1) as integer)
            when "BuildingYear" like '平成%' then
                1988 + cast(regexp_extract("BuildingYear", '平成(\d+)年', 1) as integer)
            when "BuildingYear" like '昭和%' then
                1925 + cast(regexp_extract("BuildingYear", '昭和(\d+)年', 1) as integer)
            when regexp_matches("BuildingYear", '^\d{4}年?$') then
                cast(regexp_extract("BuildingYear", '(\d{4})', 1) as integer)
            else null
        end as building_year,

        -- 取引時点
        "Period" as trade_period,
        cast(regexp_extract("Period", '(\d{4})年', 1) as integer) as trade_year,
        cast(regexp_extract("Period", '第(\d)四半期', 1) as integer) as trade_quarter,

        -- その他
        "CityPlanning" as city_planning

    from source
    where "TradePrice" is not null
      and "TradePrice" != ''
      and "Area" is not null
      and "Area" != ''
)

select * from cleaned
where trade_price > 0
  and area_sqm > 0
  and building_year is not null
