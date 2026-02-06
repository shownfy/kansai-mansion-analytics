{{ config(materialized='table') }}

-- 市区町村ディメンション（平均単価統計を含む）
with municipalities as (
    select distinct
        prefecture,
        municipality
    from {{ ref('stg_transactions') }}
),

price_stats as (
    select
        municipality,
        count(*) as transaction_count,
        avg(trade_price / area_sqm) as avg_price_per_sqm,
        percentile_cont(0.5) within group (order by trade_price / area_sqm) as median_price_per_sqm,
        min(trade_price / area_sqm) as min_price_per_sqm,
        max(trade_price / area_sqm) as max_price_per_sqm
    from {{ ref('stg_transactions') }}
    where area_sqm > 0
    group by municipality
)

select
    row_number() over (order by m.prefecture, m.municipality) as municipality_id,
    m.prefecture,
    m.municipality,
    dp.prefecture_id,
    coalesce(ps.transaction_count, 0) as transaction_count,
    coalesce(ps.avg_price_per_sqm, 0) as avg_price_per_sqm,
    coalesce(ps.median_price_per_sqm, 0) as median_price_per_sqm,
    coalesce(ps.min_price_per_sqm, 0) as min_price_per_sqm,
    coalesce(ps.max_price_per_sqm, 0) as max_price_per_sqm,
    -- エリアランク（平均単価に基づく）
    case
        when ps.avg_price_per_sqm >= 600000 then 'A'
        when ps.avg_price_per_sqm >= 400000 then 'B'
        else 'C'
    end as area_rank
from municipalities m
left join price_stats ps on m.municipality = ps.municipality
left join {{ ref('dim_prefecture') }} dp on m.prefecture = dp.prefecture_name
