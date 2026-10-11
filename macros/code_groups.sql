{#
  Group HCPCS codes the way the CPT book is organized. Five-digit numeric
  codes compare correctly as text because they all have the same length;
  the regex guard keeps alphanumeric codes such as 1234T out of the ranges.
#}

{% macro code_family(code) %}
case
    when regexp_full_match({{ code }}, '[0-9]{4}F') then 'Category II (quality reporting)'
    when regexp_full_match({{ code }}, '[0-9]{4}T') then 'Category III (emerging technology)'
    when regexp_full_match({{ code }}, '[0-9]{4}[UM]') then 'Lab analyses (PLA and MAAA)'
    when regexp_full_match({{ code }}, '[A-Z][0-9A-Z]{4}') then 'HCPCS Level II'
    when regexp_full_match({{ code }}, '[0-9]{5}') then
        case
            when {{ code }} between '00100' and '01999' then 'Anesthesia'
            when {{ code }} between '10004' and '69990' then 'Surgery'
            when {{ code }} between '70010' and '79999' then 'Radiology'
            when {{ code }} between '80047' and '89398' then 'Pathology and lab'
            when {{ code }} between '99202' and '99499' then 'Evaluation and management'
            when {{ code }} between '90281' and '99607' then 'Medicine'
            else 'Other CPT'
        end
    else 'Other'
end
{% endmacro %}


{% macro surgery_system(code) %}
case
    when not regexp_full_match({{ code }}, '[0-9]{5}') then null
    when {{ code }} between '10004' and '19499' then 'Integumentary'
    when {{ code }} between '20100' and '29999' then 'Musculoskeletal'
    when {{ code }} between '30000' and '32999' then 'Respiratory'
    when {{ code }} between '33016' and '37799' then 'Cardiovascular'
    when {{ code }} between '38100' and '38999' then 'Hemic and lymphatic'
    when {{ code }} between '39000' and '39599' then 'Mediastinum and diaphragm'
    when {{ code }} between '40490' and '49999' then 'Digestive'
    when {{ code }} between '50010' and '53899' then 'Urinary'
    when {{ code }} between '54000' and '55899' then 'Male genital'
    when {{ code }} between '55920' and '58999' then 'Female genital'
    when {{ code }} between '59000' and '59899' then 'Maternity care and delivery'
    when {{ code }} between '60000' and '60699' then 'Endocrine'
    when {{ code }} between '61000' and '64999' then 'Nervous system'
    when {{ code }} between '65091' and '68899' then 'Eye and ocular adnexa'
    when {{ code }} between '69000' and '69979' then 'Auditory'
end
{% endmacro %}


{% macro code_key(hcpcs, modifier) %}
{{ hcpcs }} || case when {{ modifier }} = '' then '' else '-' || {{ modifier }} end
{% endmacro %}
