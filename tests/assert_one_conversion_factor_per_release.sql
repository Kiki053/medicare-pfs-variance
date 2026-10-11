-- Every row in a release and track should carry the same conversion factor.
-- If CMS ever mixes two, the release-level value in dim_release is ambiguous.

select release_id, cf_track, count(distinct conversion_factor) as distinct_cfs
from {{ ref('stg_pprrvu') }}
where conversion_factor is not null
group by release_id, cf_track
having count(distinct conversion_factor) > 1
