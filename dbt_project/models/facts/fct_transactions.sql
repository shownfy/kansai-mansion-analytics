{{ config(materialized='table') }}

-- 取引ファクトテーブル
with transactions as (
    select * from {{ ref('stg_transactions') }}
),

with_dimensions as (
    select
        t.transaction_id,

        -- ディメンションへの外部キー
        dp.prefecture_id,
        dm.municipality_id,
        ds.structure_id,
        df.floor_plan_id,

        -- メジャー（数値指標）
        t.trade_price,
        t.area_sqm,
        t.trade_price / nullif(t.area_sqm, 0) as price_per_sqm,
        t.building_year,
        t.trade_year,
        t.trade_year - t.building_year as building_age,
        coalesce(t.coverage_ratio, 60) as coverage_ratio,
        coalesce(t.floor_area_ratio, 200) as floor_area_ratio,

        -- 時間ディメンション
        t.trade_year as year,
        t.trade_quarter as quarter,

        -- 元データ参照用
        t.district_name,
        t.city_planning

    from transactions t
    left join {{ ref('dim_prefecture') }} dp
        on t.prefecture = dp.prefecture_name
    left join {{ ref('dim_municipality') }} dm
        on t.municipality = dm.municipality
    left join {{ ref('dim_structure') }} ds
        on t.structure_raw = ds.structure_name_raw
    left join {{ ref('dim_floor_plan') }} df
        on t.floor_plan_raw = df.floor_plan_name
)

select * from with_dimensions
where building_age >= 0
  and building_age <= 100
  and area_sqm between 10 and 500
