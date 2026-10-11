-- Grain: one row per HCPCS code x modifier x calendar year.
-- Uses each year's primary release and, for 2026, the file that lists every
-- code (non-QP). A separate flag marks the 2026 codes where the higher
-- qualifying-APM conversion factor can apply.

with releases as (

    select release_id, is_primary
    from {{ ref('releases') }}

),

rvu as (

    select p.*
    from {{ ref('stg_pprrvu') }} as p
    inner join releases as r using (release_id)
    where r.is_primary

),

all_codes as (

    select * from rvu where cf_track in ('single', 'non_qp')

),

qp_codes as (

    select distinct hcpcs, modifier, calendar_year
    from rvu
    where cf_track = 'qp'

),

efficiency as (

    select hcpcs, modifier from {{ ref('stg_efficiency_adjustment') }}

)

select
    {{ code_key('a.hcpcs', 'a.modifier') }} || '-' || a.calendar_year as rvu_key,
    {{ code_key('a.hcpcs', 'a.modifier') }}                           as code_key,
    a.hcpcs,
    a.modifier,
    a.calendar_year,
    a.release_id,
    a.status_code,
    list_contains({{ var('payable_status_codes') }}, a.status_code)  as is_payable,
    a.work_rvu,
    a.nonfac_pe_rvu,
    a.fac_pe_rvu,
    a.mp_rvu,
    a.nonfac_total_rvu,
    a.fac_total_rvu,
    a.is_nonfac_na,
    a.is_fac_na,
    a.pctc_indicator,
    a.global_days,
    q.hcpcs is not null                                               as is_qp_eligible,
    (a.calendar_year = 2026 and e.hcpcs is not null)                  as is_efficiency_adjusted
from all_codes as a
left join qp_codes as q
    on q.hcpcs = a.hcpcs
   and q.modifier = a.modifier
   and q.calendar_year = a.calendar_year
left join efficiency as e
    on a.calendar_year = 2026
   and e.hcpcs = a.hcpcs
   and e.modifier = a.modifier
