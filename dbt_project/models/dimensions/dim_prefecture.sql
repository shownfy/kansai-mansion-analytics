{{ config(materialized='table') }}

-- 府県ディメンション
with prefectures as (
    select distinct prefecture
    from {{ ref('stg_transactions') }}
)

select
    row_number() over (order by prefecture) as prefecture_id,
    prefecture as prefecture_name,
    case prefecture
        when '大阪府' then 27
        when '京都府' then 26
        when '兵庫県' then 28
        when '奈良県' then 29
        when '滋賀県' then 25
        when '和歌山県' then 30
        else 0
    end as prefecture_code,
    case prefecture
        when '大阪府' then 1
        when '京都府' then 2
        when '兵庫県' then 3
        when '奈良県' then 4
        when '滋賀県' then 5
        when '和歌山県' then 6
        else 0
    end as prefecture_rank
from prefectures
