"""Build the project's charts and headline numbers from the dbt warehouse.

Writes, for each chart, a JSON file holding a Plotly figure, its title and
subtitle, and the same numbers as a table (the chart's accessible twin).
Colors are written as roles ("role:series-1") and resolved when the chart is
drawn, so one spec renders in both light and dark mode.

Also writes analysis/output/findings.json, the numbers quoted in the README.

Usage:
    python analysis/build_charts.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
OUT = ROOT / "analysis" / "output"
CHARTS = OUT / "charts"

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
GEO_LABELS = {"US": "National", "TN": "Tennessee", "GA": "Georgia"}
SETTING_LABELS = {"non_facility": "Office (non-facility)", "facility": "Facility"}


def rows(con, sql: str) -> list[dict]:
    result = con.execute(sql)
    names = [d[0] for d in result.description]
    return [dict(zip(names, r)) for r in result.fetchall()]


def base_layout(**overrides) -> dict:
    layout = {
        "font": {"family": FONT, "size": 13, "color": "role:ink-2"},
        "paper_bgcolor": "role:surface",
        "plot_bgcolor": "role:surface",
        "margin": {"l": 56, "r": 24, "t": 24, "b": 48},
        "hoverlabel": {
            "bgcolor": "role:surface",
            "bordercolor": "role:axis",
            "font": {"family": FONT, "color": "role:ink"},
        },
        "xaxis": {
            "showgrid": False,
            "zeroline": False,
            "showline": True,
            "linecolor": "role:axis",
            "ticks": "outside",
            "tickcolor": "role:axis",
            "fixedrange": True,
        },
        "yaxis": {
            "gridcolor": "role:grid",
            "gridwidth": 1,
            "zeroline": False,
            "showline": False,
            "fixedrange": True,
        },
        "legend": {
            "orientation": "h",
            "x": 0,
            "y": 1.08,
            "xanchor": "left",
            "yanchor": "bottom",
            "font": {"color": "role:ink-2"},
        },
        "showlegend": False,
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(layout.get(key), dict):
            layout[key] = {**layout[key], **value}
        else:
            layout[key] = value
    return layout


def tidy(value):
    """Round floats to 10 significant digits. DuckDB sums in parallel, so the
    last bits of a total can change from run to run; rounding keeps the
    committed outputs from churning when nothing real changed."""
    if isinstance(value, float):
        return float(f"{value:.10g}")
    if isinstance(value, list):
        return [tidy(v) for v in value]
    if isinstance(value, dict):
        return {k: tidy(v) for k, v in value.items()}
    return value


def save_chart(chart_id: str, title: str, subtitle: str, figure: dict, table: dict, note: str = "") -> None:
    spec = {
        "id": chart_id,
        "title": title,
        "subtitle": subtitle,
        "note": note,
        "figure": figure,
        "table": table,
    }
    (CHARTS / f"{chart_id}.json").write_text(json.dumps(tidy(spec), indent=1))


def pct(value: float, digits: int = 1) -> str:
    """Signed percent with a true minus sign; small values keep a second decimal."""
    if 0 < abs(value) < 0.05:
        digits = max(digits, 2)
    return f"{value:+.{digits}f}%".replace("-", "\u2212")


# --------------------------------------------------------------------------
# 1. Conversion factor history
# --------------------------------------------------------------------------
def conversion_factor_chart(con) -> dict:
    actual = rows(con, """
        select calendar_year, conversion_factor, conversion_factor_qp
        from dim_release where is_primary order by calendar_year
    """)
    proposed = {r["cf_track"]: r["conversion_factor"] for r in rows(con, """
        select cf_track, conversion_factor from proposed_conversion_factors
    """)}
    years = [r["calendar_year"] for r in actual]
    cf = [r["conversion_factor"] for r in actual]
    cf_2026 = actual[-1]
    marker = {"size": 10, "line": {"color": "role:surface", "width": 2}}
    traces = [
        {
            "type": "scatter", "mode": "lines+markers", "name": "Everyone else",
            "x": years, "y": cf,
            "line": {"color": "role:series-1", "width": 2},
            "marker": {**marker, "color": "role:series-1"},
            "hovertemplate": "%{x}: $%{y:.4f} per RVU<extra>Everyone else</extra>",
        },
        {
            "type": "scatter", "mode": "lines+markers", "name": "Everyone else, proposed",
            "x": [2026, 2027], "y": [cf_2026["conversion_factor"], proposed["non_qp"]],
            "line": {"color": "role:series-1", "width": 2, "dash": "dot"},
            "marker": {**marker, "color": ["role:series-1", "role:surface"],
                        "line": {"color": "role:series-1", "width": 2}},
            "hovertemplate": "%{x} proposed: $%{y:.4f}<extra>Everyone else</extra>",
            "showlegend": False,
        },
        {
            "type": "scatter", "mode": "lines+markers", "name": "Qualifying APM participants",
            "x": [2026, 2027], "y": [cf_2026["conversion_factor_qp"], proposed["qp"]],
            "line": {"color": "role:series-2", "width": 2, "dash": "dot"},
            "marker": {**marker, "color": ["role:series-2", "role:surface"],
                        "line": {"color": "role:series-2", "width": 2}},
            "hovertemplate": "%{x}: $%{y:.4f}<extra>Qualifying APM participants</extra>",
        },
    ]
    annotations = [
        {"x": 2022, "y": cf[0], "text": f"${cf[0]:.2f}", "showarrow": False,
         "yshift": 16, "font": {"color": "role:ink"}},
        {"x": 2027, "y": proposed["qp"], "text": f"${proposed['qp']:.2f}", "showarrow": False,
         "xanchor": "left", "xshift": 10, "font": {"color": "role:ink"}},
        {"x": 2027, "y": proposed["non_qp"], "text": f"${proposed['non_qp']:.2f}", "showarrow": False,
         "xanchor": "left", "xshift": 10, "font": {"color": "role:ink"}},
        {"x": 2025, "y": cf[3], "text": f"${cf[3]:.2f}", "showarrow": False,
         "yshift": -18, "font": {"color": "role:ink"}},
    ]
    figure = {
        "data": traces,
        "layout": base_layout(
            showlegend=True,
            height=340,
            margin={"r": 64},
            xaxis={"tickmode": "array", "tickvals": years + [2027],
                   "ticktext": [str(y) for y in years] + ["2027<br>proposed"],
                   "range": [2021.6, 2027.5]},
            yaxis={"tickprefix": "$", "tickformat": ".0f", "range": [31.5, 35.5], "dtick": 1},
            annotations=annotations,
        ),
    }
    table_rows = [
        [str(r["calendar_year"]), f"${r['conversion_factor']:.4f}",
         f"${r['conversion_factor_qp']:.4f}" if r["calendar_year"] >= 2026 else "same",
         "Final"]
        for r in actual
    ] + [["2027", f"${proposed['non_qp']:.4f}", f"${proposed['qp']:.4f}", "Proposed (July 2026)"]]
    save_chart(
        "conversion_factor",
        "The conversion factor fell three years running, then rose in 2026",
        "Medicare physician fee schedule conversion factor, dollars per RVU",
        figure,
        {"columns": ["Year", "Everyone else", "Qualifying APM participants", "Status"], "rows": table_rows},
        note=("2024 shows the $33.2875 rate paid from March 9 to December 31; January 1 to March 8 "
              "paid $32.7442. 2027 is CMS's July 2026 proposal and may change in the final rule."),
    )
    return {
        "cf": {str(r["calendar_year"]): r["conversion_factor"] for r in actual},
        "cf_qp_2026": cf_2026["conversion_factor_qp"],
        "cf_2027_proposed": proposed,
    }


def span(values: list[float]) -> str:
    """Describe magnitudes in words: 'about 7%' when they round alike, else '5 to 6%'."""
    rounded = sorted({round(abs(v)) for v in values})
    if len(rounded) == 1:
        return f"about {rounded[0]}%"
    return f"{rounded[0]} to {rounded[-1]}%"


def basket_coverage(con) -> dict:
    """Share of 2024 allowed dollars for fee-schedule services that the fixed basket prices."""
    data = rows(con, """
        with util as (
            select geography, hcpcs, setting, services * avg_allowed_amount as allowed
            from stg_utilization_2024
            where not is_drug
        ),
        payable as (
            select distinct hcpcs from fct_rvu where calendar_year = 2024 and is_payable
        ),
        basket as (
            select distinct geography, hcpcs, setting
            from mart_volume_weighted_change
            where current_year = 2026
        )
        select
            u.geography,
            sum(u.allowed) filter (where b.hcpcs is not null)
                / sum(u.allowed) filter (where p.hcpcs is not null) as share
        from util as u
        left join payable as p using (hcpcs)
        left join basket as b using (geography, hcpcs, setting)
        group by u.geography
    """)
    return {r["geography"]: 100 * r["share"] for r in data}


# --------------------------------------------------------------------------
# 2. 2025 -> 2026 bridge, volume-weighted, by geography
# --------------------------------------------------------------------------
def bridge_chart(con) -> dict:
    data = rows(con, """
        select geography,
            sum(prior_spend)      as prior_spend,
            sum(current_spend)    as current_spend,
            sum(cf_effect)        as cf_effect,
            sum(work_rvu_effect)  as work_rvu_effect,
            sum(pe_rvu_effect)    as pe_rvu_effect,
            sum(mp_rvu_effect)    as mp_rvu_effect,
            sum(gpci_effect)      as gpci_effect,
            sum(spend_change)     as spend_change
        from mart_volume_weighted_change
        where current_year = 2026
        group by geography
    """)
    by_geo = {r["geography"]: r for r in data}
    steps = [
        ("cf_effect", "Conversion factor"),
        ("work_rvu_effect", "Work RVUs"),
        ("pe_rvu_effect", "Practice expense"),
        ("mp_rvu_effect", "Malpractice"),
        ("gpci_effect", "Geographic index"),
    ]
    order = ["US", "TN", "GA"]
    categories = [label for _, label in steps] + ["Net change"]
    traces = []
    annotations = []
    for i, geo in enumerate(order, start=1):
        suffix = "" if i == 1 else str(i)
        r = by_geo[geo]
        base = r["prior_spend"]
        values = [100 * r[key] / base for key, _ in steps]
        total = 100 * r["spend_change"] / base
        traces.append({
            "type": "waterfall",
            "orientation": "h",
            "name": GEO_LABELS[geo],
            "y": categories,
            "x": values + [total],
            "measure": ["relative"] * len(values) + ["total"],
            "text": [pct(v) if not (geo == "US" and key == "gpci_effect") else "No adjustment"
                     for v, (key, _) in zip(values, steps)] + [pct(total)],
            "textposition": "outside",
            "textfont": {"color": "role:ink", "size": 12},
            "cliponaxis": False,
            "increasing": {"marker": {"color": "role:up"}},
            "decreasing": {"marker": {"color": "role:down"}},
            "totals": {"marker": {"color": "role:total"}},
            "connector": {"line": {"color": "role:axis", "width": 1}},
            "width": 0.56,
            "hovertemplate": "%{y}: %{x:+.2f}% of 2025 payments<extra>" + GEO_LABELS[geo] + "</extra>",
            "xaxis": f"x{suffix}",
            "yaxis": f"y{suffix}",
        })
        annotations.append({
            "text": f"<b>{GEO_LABELS[geo]}</b>", "showarrow": False,
            "xref": f"x{suffix} domain", "yref": "paper", "x": 0, "y": 1.0,
            "xanchor": "left", "yanchor": "bottom",
            "font": {"color": "role:ink", "size": 13},
        })
    domains = [[0.0, 0.27], [0.365, 0.635], [0.73, 1.0]]
    layout = base_layout(height=330, margin={"l": 132, "t": 36, "r": 40, "b": 40}, annotations=annotations)
    for i, domain in enumerate(domains, start=1):
        suffix = "" if i == 1 else str(i)
        x = {**layout["xaxis"], "domain": domain, "anchor": f"y{suffix}", "range": [0, 4.4],
             "dtick": 1, "ticksuffix": "%", "showline": False, "showgrid": True,
             "gridcolor": "role:grid", "ticks": ""}
        if i > 1:
            x["matches"] = "x"
        layout[f"xaxis{suffix}"] = x
        y = {**layout["yaxis"], "anchor": f"x{suffix}", "autorange": "reversed",
             "showgrid": False, "showticklabels": i == 1, "ticks": ""}
        if i > 1:
            y["matches"] = "y"
        layout[f"yaxis{suffix}"] = y
    figure = {"data": traces, "layout": layout}

    coverage = basket_coverage(con)
    low, high = min(coverage.values()), max(coverage.values())
    coverage_text = f"about {low:.0f}%" if round(low) == round(high) else f"about {low:.0f} to {high:.0f}%"

    table_rows = []
    for geo in order:
        r = by_geo[geo]
        base = r["prior_spend"]
        cells = [pct(100 * r[k] / base, 2) if not (geo == "US" and k == "gpci_effect") else "No adjustment"
                 for k, _ in steps]
        table_rows.append([GEO_LABELS[geo]] + cells + [pct(100 * r["spend_change"] / base, 2)])
    save_chart(
        "bridge_2026",
        "2026's net raise is smaller than the conversion factor bump",
        "What drove the 2025 to 2026 payment change, as a share of 2025 payments, holding 2024 Medicare service volume fixed",
        figure,
        {"columns": ["Geography", "Conversion factor", "Work RVUs", "Practice expense", "Malpractice",
                     "Geographic (GPCI)", "Net change"], "rows": table_rows},
        note=(f"Covers codes with one price per setting, {coverage_text} of 2024 allowed dollars for "
              "services paid from the fee schedule; codes billed in separate professional and technical "
              "pieces are left out. Georgia's statewide volume is priced at Rest of Georgia rates, the "
              "locality that includes Dalton."),
    )
    return {
        geo: {
            "net_pct": 100 * r["spend_change"] / r["prior_spend"],
            "cf_pct": 100 * r["cf_effect"] / r["prior_spend"],
            "work_pct": 100 * r["work_rvu_effect"] / r["prior_spend"],
            "pe_pct": 100 * r["pe_rvu_effect"] / r["prior_spend"],
            "mp_pct": 100 * r["mp_rvu_effect"] / r["prior_spend"],
            "gpci_pct": 100 * r["gpci_effect"] / r["prior_spend"],
            "spend_change": r["spend_change"],
            "basket_share_of_fee_schedule_dollars": coverage[geo],
        }
        for geo, r in by_geo.items()
    }


# --------------------------------------------------------------------------
# 3. Office vs facility
# --------------------------------------------------------------------------
def setting_chart(con) -> dict:
    data = rows(con, """
        select geography, setting,
            100 * sum(spend_change) / sum(prior_spend) as change_pct,
            100 * sum(pe_rvu_effect) / sum(prior_spend) as pe_pct
        from mart_volume_weighted_change
        where current_year = 2026
        group by geography, setting
    """)
    lookup = {(r["geography"], r["setting"]): r for r in data}
    order = ["US", "TN", "GA"]
    traces = []
    for setting, role in [("non_facility", "role:series-1"), ("facility", "role:series-2")]:
        values = [lookup[(g, setting)]["change_pct"] for g in order]
        traces.append({
            "type": "bar",
            "orientation": "h",
            "name": SETTING_LABELS[setting],
            "y": [GEO_LABELS[g] for g in order],
            "x": values,
            "marker": {"color": role, "cornerradius": 4},
            "text": [pct(v) for v in values],
            "textposition": "outside",
            "textfont": {"color": "role:ink", "size": 12},
            "cliponaxis": False,
            "hovertemplate": "%{y}, " + SETTING_LABELS[setting].lower() + ": %{x:+.2f}%<extra></extra>",
        })
    figure = {
        "data": traces,
        "layout": base_layout(
            showlegend=True,
            height=300,
            barmode="group",
            bargap=0.42,
            bargroupgap=0.08,
            margin={"l": 88, "r": 48},
            xaxis={"ticksuffix": "%", "range": [-9.5, 11], "dtick": 3, "showline": False,
                   "showgrid": True, "gridcolor": "role:grid", "ticks": "",
                   "zeroline": True, "zerolinecolor": "role:axis", "zerolinewidth": 1},
            yaxis={"showgrid": False, "autorange": "reversed", "ticks": ""},
            legend={"traceorder": "normal"},
        ),
    }
    table_rows = [
        [GEO_LABELS[g], pct(lookup[(g, "non_facility")]["change_pct"], 2), pct(lookup[(g, "facility")]["change_pct"], 2)]
        for g in order
    ]
    office = [lookup[(g, "non_facility")]["change_pct"] for g in order]
    facility = [lookup[(g, "facility")]["change_pct"] for g in order]
    save_chart(
        "setting_split",
        f"Office services gained {span(office)}; facility services lost {span(facility)}",
        "Change in payment from 2025 to 2026 rates on 2024 Medicare volume, by where the service was performed",
        figure,
        {"columns": ["Geography", "Office (non-facility)", "Facility"], "rows": table_rows},
        note=("CMS cut the indirect practice expense it assigns to facility-based services in 2026, "
              "reasoning that physicians employed by hospitals don't carry separate office costs."),
    )
    return {f"{g}_{s}": lookup[(g, s)]["change_pct"] for g in order for s in ["non_facility", "facility"]}


# --------------------------------------------------------------------------
# 4. Who took the efficiency adjustment
# --------------------------------------------------------------------------
def efficiency_chart(con) -> dict:
    data = rows(con, """
        with adjusted as (
            select distinct hcpcs from stg_efficiency_adjustment
        ),
        volume as (
            select hcpcs, sum(services) as services
            from stg_utilization_2024
            where geography = 'US' and not is_drug
            group by hcpcs
        ),
        codes as (
            select c.hcpcs, c.code_family
            from dim_code as c
            inner join fct_rvu as r on r.code_key = c.code_key and r.calendar_year = 2026
            where c.modifier = '' and r.is_payable and r.work_rvu > 0
        )
        select
            code_family,
            sum(services)                                                        as services,
            sum(case when a.hcpcs is not null then services else 0 end)          as adjusted_services,
            count(*)                                                             as codes,
            count(a.hcpcs)                                                       as adjusted_codes
        from codes
        inner join volume using (hcpcs)
        left join adjusted as a using (hcpcs)
        group by code_family
        having sum(services) > 1000000
        order by adjusted_services / sum(services)
    """)
    families = [r["code_family"] for r in data]
    shares = [100 * r["adjusted_services"] / r["services"] for r in data]
    labels = [f"{s:.0f}%" if s > 0 else "0%, exempt as time-based" for s in shares]
    figure = {
        "data": [{
            "type": "bar",
            "orientation": "h",
            "x": shares,
            "y": families,
            "marker": {"color": "role:series-1", "cornerradius": 4},
            "width": 0.5,
            "text": labels,
            "textposition": "outside",
            "textfont": {"color": "role:ink", "size": 12},
            "cliponaxis": False,
            "customdata": [[r["services"] / 1e6] for r in data],
            "hovertemplate": "%{y}: %{x:.1f}% of %{customdata[0]:.1f}M services<extra></extra>",
        }],
        "layout": base_layout(
            height=300,
            margin={"l": 196, "r": 48},
            xaxis={"ticksuffix": "%", "range": [0, 112], "dtick": 25, "showline": False,
                   "showgrid": True, "gridcolor": "role:grid", "ticks": ""},
            yaxis={"showgrid": False, "ticks": ""},
        ),
    }
    table_rows = [
        [r["code_family"], f"{r['services'] / 1e6:.1f}M", f"{100 * r['adjusted_services'] / r['services']:.1f}%",
         f"{r['adjusted_codes']:,} of {r['codes']:,}"]
        for r in reversed(data)
    ]
    summary = rows(con, """
        select count(*) as payable, sum(is_efficiency_adjusted::int) as adjusted
        from fct_rvu
        where calendar_year = 2026 and is_payable and modifier = '' and work_rvu > 0
    """)[0]
    save_chart(
        "efficiency_adjustment",
        "The 2.5% efficiency cut hit procedures, not office visits",
        "Share of 2024 Medicare services in each code family billed on codes CMS listed for the CY 2026 efficiency adjustment",
        figure,
        {"columns": ["Code family", "2024 services", "Share on adjusted codes", "Adjusted codes"], "rows": table_rows},
        note=("Time-based services (E/M visits, care management, behavioral health), telehealth-list "
              "services, and new 2026 codes were exempt. Families under 1 million services are omitted."),
    )
    return {"adjusted_codes": summary["adjusted"], "payable_codes_with_work": summary["payable"]}


# --------------------------------------------------------------------------
# 5. Dalton vs Chattanooga: GPCIs
# --------------------------------------------------------------------------
def gpci_chart(con) -> dict:
    data = rows(con, """
        select locality_key, calendar_year, pw_gpci, pe_gpci, mp_gpci
        from dim_locality
        where locality_key in ('GA-99', 'TN-35')
        order by locality_key, calendar_year
    """)
    series = {
        "GA-99": ("Rest of Georgia (Dalton)", "role:series-1"),
        "TN-35": ("Tennessee (Chattanooga)", "role:series-2"),
    }
    panels = [("pw_gpci", "Work"), ("pe_gpci", "Practice expense"), ("mp_gpci", "Malpractice")]
    domains = [[0.0, 0.28], [0.36, 0.64], [0.72, 1.0]]
    traces, annotations = [], []
    for i, (column, label) in enumerate(panels, start=1):
        suffix = "" if i == 1 else str(i)
        for key, (name, role) in series.items():
            points = [r for r in data if r["locality_key"] == key]
            traces.append({
                "type": "scatter", "mode": "lines+markers", "name": name,
                "legendgroup": key, "showlegend": i == 1,
                "x": [r["calendar_year"] for r in points],
                "y": [r[column] for r in points],
                "line": {"color": role, "width": 2},
                "marker": {"color": role, "size": 10, "line": {"color": "role:surface", "width": 2}},
                "hovertemplate": "%{x}: %{y:.3f}<extra>" + name + " · " + label + "</extra>",
                "xaxis": f"x{suffix}", "yaxis": f"y{suffix}",
            })
        if column == "mp_gpci":  # the gap is the story; label only where the lines separate
            last = {k: [r for r in data if r["locality_key"] == k][-1][column] for k in series}
            for key in series:
                annotations.append({
                    "x": 2026, "y": last[key], "xref": f"x{suffix}", "yref": f"y{suffix}",
                    "text": f"{last[key]:.3f}", "showarrow": False, "xanchor": "left", "xshift": 8,
                    "font": {"color": "role:ink", "size": 12},
                })
        if column == "pw_gpci":
            annotations.append({
                "x": 2024, "y": 1.0, "xref": f"x{suffix}", "yref": f"y{suffix}",
                "text": "Both held at the 1.000 floor", "showarrow": False, "yshift": 16,
                "font": {"color": "role:ink-2", "size": 11},
            })
        if column == "pe_gpci":
            annotations.append({
                "x": 2024, "y": 0.9, "xref": f"x{suffix}", "yref": f"y{suffix}",
                "text": "Within 0.02 of each other", "showarrow": False, "yshift": 18,
                "font": {"color": "role:ink-2", "size": 11},
            })
        annotations.append({
            "text": f"<b>{label}</b>", "showarrow": False, "xref": f"x{suffix} domain",
            "yref": "paper", "x": 0, "y": 1.0, "yanchor": "bottom", "xanchor": "left",
            "font": {"color": "role:ink", "size": 13},
        })
    layout = base_layout(showlegend=True, height=320, margin={"t": 72, "r": 40},
                         annotations=annotations, legend={"y": 1.18})
    for i, domain in enumerate(domains, start=1):
        suffix = "" if i == 1 else str(i)
        layout[f"xaxis{suffix}"] = {**layout["xaxis"], "domain": domain, "anchor": f"y{suffix}",
                                     "tickvals": [2022, 2024, 2026], "range": [2021.6, 2026.9]}
        y = {**layout["yaxis"], "anchor": f"x{suffix}", "range": [0.4, 1.3], "dtick": 0.2,
             "tickformat": ".1f", "showticklabels": i == 1}
        if i > 1:
            y["matches"] = "y"
        layout[f"yaxis{suffix}"] = y
    figure = {"data": traces, "layout": layout}

    comparison = rows(con, """
        select setting,
            median(rest_of_georgia_payment / tennessee_payment - 1) * 100 as median_premium,
            count(*) as codes
        from mart_local_comparison
        where calendar_year = 2026 and modifier = '' and tennessee_payment > 0
        group by setting
    """)
    premium = {r["setting"]: r["median_premium"] for r in comparison}
    by_key = {(r["locality_key"], r["calendar_year"]): r for r in data}
    table_rows = [
        [str(year)] + [f"{by_key[(k, year)][c]:.3f}" for c, _ in panels for k in series]
        for year in sorted({r["calendar_year"] for r in data})
    ]
    columns = ["Year"] + [f"{label}, {'Dalton' if k == 'GA-99' else 'Chattanooga'}"
                          for _, label in panels for k in series]
    save_chart(
        "local_gpci",
        "Georgia's malpractice adjustment is more than double Tennessee's",
        "Medicare geographic practice cost indices, 1.000 = national average",
        figure,
        {"columns": columns, "rows": table_rows},
        note=(f"For the same service in a facility, Medicare paid a median {premium['facility']:.1f}% more in "
              f"Dalton than in Chattanooga in 2026; in an office, {premium['non_facility']:.1f}% more, because "
              "Tennessee's higher practice expense index offsets most of the gap."),
    )
    return {
        "median_dalton_premium_facility": premium["facility"],
        "median_dalton_premium_office": premium["non_facility"],
        "mp_gpci_2026": {k: by_key[(k, 2026)]["mp_gpci"] for k in series},
        "mp_gpci_2022": {k: by_key[(k, 2022)]["mp_gpci"] for k in series},
    }


# --------------------------------------------------------------------------
# 6. Example codes table
# --------------------------------------------------------------------------
# Plain-language labels for the example codes. CPT descriptors are AMA
# copyright, so the published outputs describe codes in their own words.
EXAMPLE_LABELS = {
    "99214": "Office visit, established patient, 30 to 39 minutes",
    "99213": "Office visit, established patient, 20 to 29 minutes",
    "27447": "Total knee replacement",
    "66984": "Cataract surgery with lens implant",
    "45378": "Diagnostic colonoscopy",
    "20610": "Large joint injection or aspiration",
}


def example_codes(con) -> list[dict]:
    picks = [
        ("99214", "non_facility"), ("99214", "facility"), ("99213", "non_facility"),
        ("27447", "facility"), ("66984", "facility"), ("45378", "facility"),
        ("45378", "non_facility"), ("20610", "non_facility"),
    ]
    data = rows(con, f"""
        select v.code_key, v.setting, v.prior_payment, v.current_payment,
               v.payment_change_pct, v.cf_effect, v.work_rvu_effect, v.pe_rvu_effect, v.mp_rvu_effect
        from mart_payment_variance as v
        where v.locality_key = 'US-00' and v.current_year = 2026
          and (v.code_key, v.setting) in ({", ".join(f"('{c}', '{s}')" for c, s in picks)})
    """)
    lookup = {(r["code_key"], r["setting"]): r for r in data}
    out = []
    for code, setting in picks:
        r = lookup[(code, setting)]
        out.append({
            "code": code,
            "service": EXAMPLE_LABELS[code],
            "setting": SETTING_LABELS[setting],
            "payment_2025": round(r["prior_payment"], 2),
            "payment_2026": round(r["current_payment"], 2),
            "change_pct": round(100 * r["payment_change_pct"], 1),
            "cf_effect": round(r["cf_effect"], 2),
            "work_rvu_effect": round(r["work_rvu_effect"], 2),
            "pe_rvu_effect": round(r["pe_rvu_effect"], 2),
            "mp_rvu_effect": round(r["mp_rvu_effect"], 2),
        })
    return out


# --------------------------------------------------------------------------
# Phone-width versions. Small multiples stack vertically, long category
# labels move above their bars, and ticks thin out so nothing rotates.
# --------------------------------------------------------------------------
def _stack_panels(layout: dict, domains: list[list[float]]) -> None:
    for i, domain in enumerate(domains, start=1):
        suffix = "" if i == 1 else str(i)
        layout[f"xaxis{suffix}"]["domain"] = [0, 1]
        layout[f"yaxis{suffix}"]["domain"] = domain
        layout[f"yaxis{suffix}"]["showticklabels"] = True
    for ann in layout.get("annotations", []):
        if ann.get("yref") == "paper" and str(ann.get("xref", "")).endswith("domain"):
            axis = ann["xref"].split()[0][1:]
            ann["yref"] = f"y{axis} domain"
            ann["y"] = 1.0
            ann["yanchor"] = "bottom"


def narrow_conversion_factor(fig: dict) -> dict:
    f = copy.deepcopy(fig)
    lay = f["layout"]
    lay["height"] = 320
    lay["margin"] = {**lay["margin"], "l": 44, "r": 56, "t": 64}
    lay["xaxis"]["tickvals"] = [2022, 2024, 2026, 2027]
    lay["xaxis"]["ticktext"] = ["2022", "2024", "2026", "2027<br>proposed"]
    lay["xaxis"]["tickangle"] = 0
    lay["legend"] = {**lay["legend"], "y": 1.04}
    for ann in lay["annotations"]:
        if ann["x"] == 2022:
            ann.update({"xanchor": "left", "xshift": 8, "yshift": 12})
    return f


def narrow_bridge(fig: dict) -> dict:
    f = copy.deepcopy(fig)
    lay = f["layout"]
    lay["height"] = 680
    lay["margin"] = {"l": 124, "r": 48, "t": 28, "b": 32}
    _stack_panels(lay, [[0.71, 1.0], [0.355, 0.645], [0.0, 0.29]])
    for ann in lay["annotations"]:
        ann["xshift"] = -120
    return f


def narrow_setting(fig: dict) -> dict:
    f = copy.deepcopy(fig)
    lay = f["layout"]
    lay["margin"] = {**lay["margin"], "l": 80, "r": 40, "t": 64}
    lay["xaxis"]["range"] = [-13, 12.5]
    lay["xaxis"]["dtick"] = 4
    lay["legend"] = {**lay["legend"], "y": 1.04}
    return f


def narrow_efficiency(fig: dict) -> dict:
    f = copy.deepcopy(fig)
    lay = f["layout"]
    trace = f["data"][0]
    trace["width"] = 0.38
    lay["height"] = 400
    # leave room for the "0%" tick, which Plotly hides if it would spill past the div
    lay["margin"] = {**lay["margin"], "l": 16, "r": 16, "t": 8}
    lay["yaxis"]["showticklabels"] = False
    lay["xaxis"]["dtick"] = 50
    lay["xaxis"]["range"] = [0, 118]
    lay["annotations"] = lay.get("annotations", []) + [
        {"x": 0, "y": category, "xref": "x", "yref": "y", "text": category, "showarrow": False,
         "xanchor": "left", "yanchor": "bottom", "yshift": 13,
         "font": {"color": "role:ink-2", "size": 12}}
        for category in trace["y"]
    ]
    return f


def narrow_gpci(fig: dict) -> dict:
    f = copy.deepcopy(fig)
    lay = f["layout"]
    lay["height"] = 620
    lay["margin"] = {"l": 44, "r": 56, "t": 96, "b": 32}
    lay["legend"] = {**lay["legend"], "y": 1.1}
    _stack_panels(lay, [[0.72, 1.0], [0.36, 0.64], [0.0, 0.28]])
    # the panels share one set of years, so only the bottom panel labels them
    lay["xaxis"]["showticklabels"] = False
    lay["xaxis2"]["showticklabels"] = False
    return f


NARROW = {
    "conversion_factor": narrow_conversion_factor,
    "bridge_2026": narrow_bridge,
    "setting_split": narrow_setting,
    "efficiency_adjustment": narrow_efficiency,
    "local_gpci": narrow_gpci,
}


def add_narrow_versions() -> None:
    for chart_id, make in NARROW.items():
        path = CHARTS / f"{chart_id}.json"
        spec = json.loads(path.read_text())
        spec["figure_narrow"] = make(spec["figure"])
        path.write_text(json.dumps(tidy(spec), indent=1))


def main() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    findings = {
        "conversion_factor": conversion_factor_chart(con),
        "bridge_2026": bridge_chart(con),
        "setting_2026": setting_chart(con),
        "efficiency_adjustment": efficiency_chart(con),
        "local": gpci_chart(con),
        "example_codes": example_codes(con),
    }
    add_narrow_versions()
    (OUT / "findings.json").write_text(json.dumps(tidy(findings), indent=2))
    print(f"Wrote {len(list(CHARTS.glob('*.json')))} charts and findings.json to {OUT}")


if __name__ == "__main__":
    main()
