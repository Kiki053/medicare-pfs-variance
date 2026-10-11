-- One row per HCPCS code x modifier seen in any primary release.

with codes as (

    select
        p.hcpcs,
        p.modifier,
        p.description,
        p.calendar_year
    from {{ ref('stg_pprrvu') }} as p
    inner join {{ ref('releases') }} as r using (release_id)
    where r.is_primary
      and p.cf_track in ('single', 'non_qp')

),

collapsed as (

    select
        hcpcs,
        modifier,
        arg_max(description, calendar_year) as description,
        min(calendar_year)                  as first_year,
        max(calendar_year)                  as last_year
    from codes
    group by hcpcs, modifier

)

select
    {{ code_key('hcpcs', 'modifier') }}                   as code_key,
    hcpcs,
    modifier,
    description,
    {{ code_family('hcpcs') }}                            as code_family,
    {{ surgery_system('hcpcs') }}                         as surgery_system,
    first_year,
    last_year
from collapsed
