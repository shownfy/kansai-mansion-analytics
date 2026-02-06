{{ config(materialized='table') }}

-- 建物構造ディメンション
with structures as (
    select distinct structure_raw
    from {{ ref('stg_transactions') }}
    where structure_raw is not null
),

normalized as (
    select
        structure_raw,
        case
            when structure_raw like '%RC%' or structure_raw like '%鉄筋%' or structure_raw like '%ＲＣ%' then 'RC'
            when structure_raw like '%SRC%' or structure_raw like '%ＳＲＣ%' then 'SRC'
            when structure_raw like '%鉄骨%' or structure_raw like '%S造%' then 'S'
            when structure_raw like '%木造%' then 'Wood'
            else 'Other'
        end as structure_type
    from structures
)

select
    row_number() over (order by structure_type, structure_raw) as structure_id,
    structure_raw as structure_name_raw,
    structure_type,
    case structure_type
        when 'SRC' then 1.05
        when 'RC' then 1.00
        when 'S' then 0.92
        when 'Wood' then 0.85
        else 0.90
    end as price_factor
from normalized
