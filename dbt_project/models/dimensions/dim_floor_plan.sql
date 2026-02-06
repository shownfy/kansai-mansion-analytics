{{ config(materialized='table') }}

-- 間取りディメンション
with floor_plans as (
    select distinct floor_plan_raw
    from {{ ref('stg_transactions') }}
    where floor_plan_raw is not null
),

normalized as (
    select
        floor_plan_raw,
        -- 部屋数の抽出
        case
            when floor_plan_raw like '%1K%' or floor_plan_raw like '%1R%' or floor_plan_raw like '%１Ｋ%' or floor_plan_raw like '%１Ｒ%' then 1
            when floor_plan_raw like '%1LDK%' or floor_plan_raw like '%1DK%' or floor_plan_raw like '%１ＬＤＫ%' or floor_plan_raw like '%１ＤＫ%' then 1
            when floor_plan_raw like '%2LDK%' or floor_plan_raw like '%2DK%' or floor_plan_raw like '%2K%' or floor_plan_raw like '%２ＬＤＫ%' or floor_plan_raw like '%２ＤＫ%' then 2
            when floor_plan_raw like '%3LDK%' or floor_plan_raw like '%3DK%' or floor_plan_raw like '%3K%' or floor_plan_raw like '%３ＬＤＫ%' or floor_plan_raw like '%３ＤＫ%' then 3
            when floor_plan_raw like '%4LDK%' or floor_plan_raw like '%4DK%' or floor_plan_raw like '%4K%' or floor_plan_raw like '%４ＬＤＫ%' or floor_plan_raw like '%４ＤＫ%' then 4
            when floor_plan_raw like '%5LDK%' or floor_plan_raw like '%5DK%' or floor_plan_raw like '%５ＬＤＫ%' or floor_plan_raw like '%５ＤＫ%' then 5
            else 2
        end as num_rooms,
        -- LDKの有無
        case
            when floor_plan_raw like '%LDK%' or floor_plan_raw like '%ＬＤＫ%' then true
            else false
        end as has_ldk
    from floor_plans
)

select
    row_number() over (order by num_rooms, has_ldk, floor_plan_raw) as floor_plan_id,
    floor_plan_raw as floor_plan_name,
    num_rooms,
    has_ldk
from normalized
