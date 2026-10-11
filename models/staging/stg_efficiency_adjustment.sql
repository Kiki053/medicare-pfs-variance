-- Codes CMS listed as subject to the CY 2026 -2.5% efficiency adjustment.

with source as (

    select * from {{ source('landing', 'efficiency_adjustment_2026') }}

)

select
    upper(trim(hcpcs))                          as hcpcs,
    upper(coalesce(trim(modifier), ''))         as modifier,
    cast(work_rvu_before as double)             as work_rvu_before,
    cast(work_rvu_after as double)              as work_rvu_after,
    try_cast(nullif(total_time_before, '') as double) as total_time_before,
    try_cast(nullif(total_time_after, '') as double)  as total_time_after
from source
where hcpcs <> ''
