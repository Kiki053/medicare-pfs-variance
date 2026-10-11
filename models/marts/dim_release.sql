-- One row per CMS release, with the conversion factor(s) it carries.

with releases as (

    select * from {{ ref('releases') }}

),

conversion_factors as (

    select
        release_id,
        max(case when cf_track in ('single', 'non_qp') then conversion_factor end) as conversion_factor,
        max(case when cf_track in ('single', 'qp') then conversion_factor end)     as conversion_factor_qp,
        max(released_on)                                                         as released_on
    from {{ ref('stg_pprrvu') }}
    group by release_id

)

select
    r.release_id,
    r.calendar_year,
    r.release_label,
    r.is_primary,
    r.note,
    c.released_on,
    c.conversion_factor,
    c.conversion_factor_qp
from releases as r
inner join conversion_factors as c using (release_id)
