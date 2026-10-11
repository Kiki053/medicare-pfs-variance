-- One typed row per Medicare locality x release.

with source as (

    select * from {{ source('landing', 'gpci') }}

)

select
    release_id,
    cast(calendar_year as integer)                      as calendar_year,
    trim(mac)                                           as mac,
    upper(trim(state))                                  as state,
    -- CMS writes locality 1 as "1" in some years and "01" in others
    lpad(cast(cast(locality_number as integer) as varchar), 2, '0') as locality_number,
    trim(locality_name)                                 as locality_name,
    cast(pw_gpci as double)                             as pw_gpci,
    try_cast(nullif(pw_gpci_no_floor, '') as double)    as pw_gpci_no_floor,
    cast(pe_gpci as double)                             as pe_gpci,
    cast(mp_gpci as double)                             as mp_gpci
from source
