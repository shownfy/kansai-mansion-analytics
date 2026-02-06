{{ config(materialized='table') }}

-- ML学習用データセット（ディメンショナルモデルから構築）
with fact as (
    select * from {{ ref('fct_transactions') }}
),

-- stg_transactionsから地区情報を取得
stg as (
    select
        transaction_id,
        prefecture,
        municipality,
        district_name
    from {{ ref('stg_transactions') }}
),

enriched as (
    select
        -- ターゲット変数
        f.trade_price,

        -- 特徴量: 物件属性
        f.area_sqm,
        f.building_age,
        fp.num_rooms,
        case when fp.has_ldk then 1 else 0 end as has_ldk,
        f.coverage_ratio,
        f.floor_area_ratio,

        -- 特徴量: 構造
        ds.structure_type,

        -- 特徴量: 地域
        dp.prefecture_rank as prefecture_code,
        dm.avg_price_per_sqm as city_avg_price_per_sqm,
        dm.avg_price_per_sqm * 1.1 as station_avg_price_per_sqm,  -- 駅周辺は1.1倍と仮定
        dm.area_rank,

        -- 特徴量: 駅距離（デフォルト値 - 予測時はユーザー入力）
        10 as time_to_station_min,
        null as nearest_station,

        -- 特徴量: 駅乗降客数（デフォルト値）
        4.48 as log_passenger_count,
        'medium' as station_rank,

        -- 特徴量: ハザードリスク（推定値）
        3.0 as total_hazard_risk,
        'medium' as hazard_risk_category,

        -- メタデータ
        f.trade_year,
        f.quarter,
        dp.prefecture_name as prefecture,
        dm.municipality

    from fact f
    inner join stg s on f.transaction_id = s.transaction_id
    left join {{ ref('dim_prefecture') }} dp on f.prefecture_id = dp.prefecture_id
    left join {{ ref('dim_municipality') }} dm on f.municipality_id = dm.municipality_id
    left join {{ ref('dim_structure') }} ds on f.structure_id = ds.structure_id
    left join {{ ref('dim_floor_plan') }} fp on f.floor_plan_id = fp.floor_plan_id
    where f.price_per_sqm is not null
      and dm.avg_price_per_sqm > 0
)

select * from enriched
