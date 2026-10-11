-- Grain: one row per code CMS listed under the CY 2026 efficiency adjustment.
-- Compares CMS's before/after work RVUs with the 2025 and 2026 files, and
-- attaches 2024 national volume so the impact can be weighted.

with listed as (

    select * from {{ ref('stg_efficiency_adjustment') }}

),

rvu as (

    select code_key, hcpcs, modifier, calendar_year, work_rvu, status_code
    from {{ ref('fct_rvu') }}
    where calendar_year in (2025, 2026)

),

national_volume as (

    select hcpcs, sum(services) as services_2024
    from {{ ref('stg_utilization_2024') }}
    where geography = 'US'
    group by hcpcs

)

select
    {{ code_key('l.hcpcs', 'l.modifier') }}                      as code_key,
    l.hcpcs,
    l.modifier,
    c.code_family,
    c.surgery_system,
    c.description,
    l.work_rvu_before                                           as cms_work_rvu_before,
    l.work_rvu_after                                            as cms_work_rvu_after,
    r25.work_rvu                                                as work_rvu_2025,
    r26.work_rvu                                                as work_rvu_2026,
    r26.status_code                                             as status_code_2026,
    case when l.work_rvu_before > 0
         then l.work_rvu_after / l.work_rvu_before - 1 end      as cms_work_rvu_change_pct,
    l.total_time_before,
    l.total_time_after,
    case when l.modifier = '' then v.services_2024 end          as national_services_2024
from listed as l
left join {{ ref('dim_code') }} as c
    on c.code_key = {{ code_key('l.hcpcs', 'l.modifier') }}
left join rvu as r25
    on r25.hcpcs = l.hcpcs and r25.modifier = l.modifier and r25.calendar_year = 2025
left join rvu as r26
    on r26.hcpcs = l.hcpcs and r26.modifier = l.modifier and r26.calendar_year = 2026
left join national_volume as v
    on v.hcpcs = l.hcpcs
