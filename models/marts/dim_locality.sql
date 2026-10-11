-- One row per Medicare locality per year. GPCIs change every year, so the
-- year is part of the key (a slowly changing dimension, versioned by year).
-- A "national" row with every GPCI at 1.000 gives the unadjusted rate.

with primary_releases as (

    select release_id, calendar_year
    from {{ ref('releases') }}
    where is_primary

),

localities as (

    select
        g.state || '-' || g.locality_number as locality_key,
        g.calendar_year,
        g.release_id,
        g.mac,
        g.state,
        g.locality_number,
        g.locality_name,
        g.pw_gpci,
        g.pw_gpci_no_floor,
        g.pe_gpci,
        g.mp_gpci
    from {{ ref('stg_gpci') }} as g
    inner join primary_releases as r using (release_id, calendar_year)

    union all

    select
        'US-00',
        calendar_year,
        release_id,
        null,
        'US',
        '00',
        'NATIONAL (NO GEOGRAPHIC ADJUSTMENT)',
        1.0,
        1.0,
        1.0,
        1.0
    from primary_releases

)

select
    locality_key || '-' || calendar_year as locality_year_key,
    *,
    case locality_key
        when 'US-00' then 'National'
        when 'TN-35' then 'Tennessee statewide (Chattanooga)'
        when 'GA-99' then 'Rest of Georgia (Dalton)'
        when 'GA-01' then 'Atlanta'
    end                                  as focus_label,
    list_contains({{ var('focus_localities') }}, locality_key) as is_focus
from localities
