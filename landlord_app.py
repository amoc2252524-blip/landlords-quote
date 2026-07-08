"""Landlord Insurance Quote Comparator — Australia.

Sister app to the Motor Quote Comparator. Same supervised three-prompt
workflow: Extract (main chat) -> Prefill (sidebar) -> Quote (sidebar).
"""

import re
from datetime import date, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Landlord Quote Comparator",
    page_icon="🏠",
    layout="wide",
)

APP_URL = "https://landlord-quote.streamlit.app"  # update after first deploy

# ---------------------------------------------------------------------------
# Insurer brands offering landlord insurance in Australia, grouped by
# underwriter / platform so duplicate quoting effort is obvious.
# ---------------------------------------------------------------------------
INSURER_GROUPS = {
    "Suncorp Group (AAI Limited)": [
        "AAMI", "GIO", "Suncorp", "Apia", "Terri Scheer",
    ],
    "IAG": [
        "NRMA", "CGU", "SGIO", "SGIC", "RACV", "Bendigo Bank",
    ],
    "Allianz (incl. bank partners)": [
        "Allianz", "Westpac", "St.George", "Bank of Melbourne", "BankSA",
        "HSBC", "NAB",
    ],
    "Hollard (incl. partner brands)": [
        "Real Insurance", "Everyday Insurance (Woolworths)", "CommBank",
        "Kogan Insurance", "Medibank", "Australian Seniors",
        "Australian Unity",
    ],
    "Auto & General": [
        "Budget Direct", "Qantas Insurance", "ING",
    ],
    "QBE (incl. partners)": [
        "QBE", "ANZ", "Elders Insurance",
    ],
    "Youi": ["Youi"],
    "Motoring clubs": [
        "RACQ", "RAC (WA)", "RAA (SA)", "RACT",
    ],
    "Landlord specialists": [
        "EBM RentCover", "St George Underwriting Agency (SGUA)",
        "Honey Insurance", "Huddle",
    ],
    "Other": [
        "Great Southern Bank", "Bupa",
    ],
}

ALL_INSURERS = [b for brands in INSURER_GROUPS.values() for b in brands]
MAX_SELECTED = 10

PROPERTY_TYPES = ["House", "Townhouse", "Unit / Apartment", "Duplex", "Villa", "Terrace"]
WALL_TYPES = ["Brick veneer", "Double brick", "Weatherboard / timber", "Fibro", "Hebel / concrete", "Mixed / other"]
ROOF_TYPES = ["Tiles (terracotta/concrete)", "Colorbond / metal", "Slate", "Other"]
COVER_TYPES = ["Building & Contents", "Building only", "Contents only"]
LEASE_TYPES = ["Fixed term lease", "Periodic (month to month)", "Between tenants / vacant", "New purchase — tenant to be found"]
STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]


def _init_state():
    if "quotes" not in st.session_state:
        st.session_state.quotes = []


def _money(v):
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _get(key, default=""):
    return st.session_state.get(key, default)


_init_state()

st.title("🏠 Landlord Insurance Quote Comparator")
st.caption("Australia-wide · supervised Claude-in-Chrome workflow · same playbook as the Motor Quote Comparator")

tab_instr, tab_prop, tab_get, tab_enter, tab_compare = st.tabs(
    ["📖 Instructions", "🏠 Property & Cover", "🤖 Get Quotes", "📝 Enter Quotes", "📊 Compare"]
)

# ===========================================================================
# TAB 2 — PROPERTY & COVER (rendered logic first so prompts can read values,
# but Streamlit renders tabs in declared order)
# ===========================================================================
with tab_prop:
    st.subheader("Policyholder")
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Full name", key="ph_name")
    c2.date_input("Date of birth", key="ph_dob", value=None,
                  min_value=date(1920, 1, 1), max_value=date.today())
    c3.text_input("Email", key="ph_email")
    c4.text_input("Mobile", key="ph_mobile")

    st.subheader("Property")
    c1, c2 = st.columns([2, 1])
    c1.text_input(
        "Property address",
        key="prop_address",
        help="Use the full format e.g. '75 Bridge St, Lane Cove NSW 2066' — "
             "state + postcode makes autocomplete reliable on insurer sites.",
    )
    c2.selectbox("State", STATES, key="prop_state")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.selectbox("Property type", PROPERTY_TYPES, key="prop_type")
    c2.number_input("Year built", min_value=1850, max_value=date.today().year,
                    value=1990, key="prop_year_built")
    c3.selectbox("External walls", WALL_TYPES, key="prop_walls")
    c4.selectbox("Roof", ROOF_TYPES, key="prop_roof")
    c5.number_input("Storeys", min_value=1, max_value=4, value=1, key="prop_storeys")
    c1, c2, c3 = st.columns(3)
    c1.number_input("Bedrooms", min_value=0, max_value=12, value=3, key="prop_beds")
    c2.number_input("Bathrooms", min_value=0, max_value=8, value=1, key="prop_baths")
    c3.selectbox("Body corporate / strata?", ["No", "Yes"], key="prop_strata",
                 help="Units and some townhouses: building is often insured by strata, "
                      "so contents-only landlord cover may be all you need.")

    st.subheader("Tenancy")
    c1, c2, c3, c4 = st.columns(4)
    c1.selectbox("Lease situation", LEASE_TYPES, key="ten_lease")
    c2.number_input("Weekly rent ($)", min_value=0, max_value=10000, value=600,
                    step=10, key="ten_rent")
    c3.selectbox("Managed by an agent?", ["Yes", "No (self-managed)"], key="ten_agent")
    c4.selectbox("Short-term / holiday letting?", ["No", "Yes"], key="ten_short",
                 help="Most landlord policies exclude short-stay letting — flag it honestly.")

    st.subheader("Cover")
    c1, c2, c3, c4 = st.columns(4)
    c1.selectbox("Cover type", COVER_TYPES, key="cov_type")
    c2.number_input("Building sum insured ($)", min_value=0, max_value=10_000_000,
                    value=650_000, step=10_000, key="cov_building_sum")
    c3.number_input("Contents sum insured ($)", min_value=0, max_value=1_000_000,
                    value=20_000, step=1_000, key="cov_contents_sum")
    c4.date_input("Cover start date", key="cov_start",
                  value=date.today() + timedelta(days=14))
    c1, c2, c3, c4 = st.columns(4)
    c1.selectbox("Rent default & tenant damage option", ["Yes — include", "No"],
                 key="cov_rent_default")
    c2.selectbox("Flood cover", ["Yes — include", "No", "Whatever is standard"],
                 key="cov_flood")
    c3.number_input("Preferred excess ($)", min_value=0, max_value=5000, value=500,
                    step=50, key="cov_excess_pref")
    c4.selectbox("Mortgage on the property?", ["Yes", "No"], key="cov_mortgage")

    st.subheader("Security & claims")
    c1, c2, c3, c4 = st.columns(4)
    c1.selectbox("Deadlocks on external doors", ["Yes", "No"], key="sec_deadlocks")
    c2.selectbox("Window locks", ["Yes", "No"], key="sec_window_locks")
    c3.selectbox("Alarm", ["None", "Local alarm", "Back-to-base"], key="sec_alarm")
    c4.selectbox("Claims in last 5 years", ["No", "Yes"], key="clm_any")
    if _get("clm_any") == "Yes":
        st.text_area("Claim details (year, type, amount)", key="clm_details")

    st.subheader("Current policy (baseline)")
    c1, c2, c3, c4 = st.columns(4)
    c1.text_input("Current insurer", key="cur_insurer")
    c2.number_input("Renewal premium ($/yr)", min_value=0.0, max_value=50_000.0,
                    value=0.0, step=10.0, key="cur_renewal_premium")
    c3.number_input("Renewal excess ($)", min_value=0.0, max_value=10_000.0,
                    value=0.0, step=50.0, key="cur_renewal_excess")
    c4.number_input("Last year's premium ($/yr)", min_value=0.0, max_value=50_000.0,
                    value=0.0, step=10.0, key="cur_last_premium")

    st.success("All fields auto-save as you type — no save button needed.")

# ===========================================================================
# Build a details block shared by the prompts
# ===========================================================================
def details_block() -> str:
    dob = _get("ph_dob")
    start = _get("cov_start")
    lines = [
        f"Policyholder: {_get('ph_name') or '[name]'} | DOB: {dob or '[dob]'} | "
        f"Email: {_get('ph_email') or '[email]'} | Mobile: {_get('ph_mobile') or '[mobile]'}",
        f"Property: {_get('prop_address') or '[address]'} ({_get('prop_state')})",
        f"Type: {_get('prop_type')} | Built: {_get('prop_year_built')} | "
        f"Walls: {_get('prop_walls')} | Roof: {_get('prop_roof')} | "
        f"Storeys: {_get('prop_storeys')} | Beds: {_get('prop_beds')} | "
        f"Baths: {_get('prop_baths')} | Strata: {_get('prop_strata')}",
        f"Tenancy: {_get('ten_lease')} | Rent: ${_get('ten_rent')}/wk | "
        f"Agent managed: {_get('ten_agent')} | Short-term letting: {_get('ten_short')}",
        f"Cover: {_get('cov_type')} | Building sum: ${_get('cov_building_sum'):,} | "
        f"Contents sum: ${_get('cov_contents_sum'):,} | Start: {start}",
        f"Rent default option: {_get('cov_rent_default')} | Flood: {_get('cov_flood')} | "
        f"Preferred excess: ${_get('cov_excess_pref')} | Mortgaged: {_get('cov_mortgage')}",
        f"Security: deadlocks {_get('sec_deadlocks')}, window locks {_get('sec_window_locks')}, "
        f"alarm {_get('sec_alarm')}",
        f"Claims last 5 yrs: {_get('clm_any')}"
        + (f" — {_get('clm_details')}" if _get('clm_any') == 'Yes' else ""),
        f"Current insurer: {_get('cur_insurer') or '[none]'} | "
        f"Renewal premium: {_money(_get('cur_renewal_premium'))} | "
        f"Renewal excess: {_money(_get('cur_renewal_excess'))}",
    ]
    return "\n".join(lines)


# ===========================================================================
# TAB 1 — INSTRUCTIONS
# ===========================================================================
with tab_instr:
    st.subheader("How this works")
    st.markdown(
        """
**1.** Open this app in Chrome with the **Claude in Chrome** extension installed.

**2.** Upload your current landlord policy / renewal PDFs to the **main Claude chat** (not the sidebar — the sidebar can't accept files).

**3.** Run the **Extract prompt** in the main chat to pull the property details out of the PDFs.

**4.** Open the **Claude sidebar** in the same window and run the **Prefill prompt** — it reads the extracted details from the main chat and fills the Property & Cover tab for you. Check every field.

**5.** Select **Sonnet** in the sidebar for speed, and enable **"act without asking"** at the bottom of the sidebar panel.

**6.** Pick your insurers in the grid below — brands in the same group share an underwriting platform, so quoting more than one per group mostly gets you the same engine with different branding. **2–3 at a time** is the reliable sweet spot (hard cap of 10).
"""
    )

    st.subheader("Select insurers to quote")
    selected = []
    for group, brands in INSURER_GROUPS.items():
        st.markdown(f"**{group}**")
        cols = st.columns(6)
        for i, brand in enumerate(brands):
            with cols[i % 6]:
                if st.checkbox(brand, key=f"sel_{brand}", value=False):
                    selected.append(brand)
    n_selected = len(selected)
    if n_selected > MAX_SELECTED:
        st.error(f"⚠️ {n_selected} selected — cap is {MAX_SELECTED}. Untick a few.")
    elif n_selected == 0:
        st.info("Tick at least one insurer to generate the quote prompt.")
    else:
        st.success(f"{n_selected} insurer(s) selected: {', '.join(selected)}")

    st.markdown(
        """
**7.** Run the **Quote prompt** (from the Get Quotes tab) in the sidebar. Claude opens each insurer in a **new tab**, keeps this app tab untouched, fills the quote forms, and **pauses for your approval before anything is submitted**.

**8.** Click **"Always allow this site"** on any extension permission prompts — Budget Direct, Youi and NRMA in particular won't proceed without it.

**9.** As results come back, paste them into the **Enter Quotes** tab (Quick Add understands the standard results line), then head to **Compare**.
"""
    )
    st.info(
        "💡 Landlord-specific gotchas: strata units usually only need **contents-only** landlord "
        "cover; most insurers exclude **short-stay letting**; **rent default** cover is often an "
        "optional extra with a tenant-on-lease requirement — make sure Claude ticks it "
        "consistently so quotes are apples-to-apples."
    )

# ===========================================================================
# TAB 3 — GET QUOTES (the three prompts)
# ===========================================================================
with tab_get:
    st.subheader("Prompt 1 — Extract (run in the MAIN Claude chat)")
    extract_prompt = """I've uploaded my landlord insurance renewal / policy documents.
Read them and output the property and policy details in EXACTLY this structure so a later prompt can use them:

Policyholder: [name] | DOB: [dob] | Email: [email] | Mobile: [mobile]
Property: [full address with state and postcode]
Type: [house/unit/etc] | Built: [year] | Walls: [construction] | Roof: [type] | Storeys: [n] | Beds: [n] | Baths: [n] | Strata: [yes/no]
Tenancy: [lease situation] | Rent: $[amount]/wk | Agent managed: [yes/no] | Short-term letting: [yes/no]
Cover: [Building & Contents / Building only / Contents only] | Building sum: $[amount] | Contents sum: $[amount] | Start: [renewal/start date]
Rent default option: [yes/no] | Flood: [yes/no] | Preferred excess: $[amount] | Mortgaged: [yes/no]
Security: deadlocks [yes/no], window locks [yes/no], alarm [none/local/back-to-base]
Claims last 5 yrs: [no / yes — details]
Current insurer: [name] | Renewal premium: $[amount] | Renewal excess: $[amount]

If something isn't in the documents, write [unknown] rather than guessing."""
    st.code(extract_prompt, language=None)

    st.subheader("Prompt 2 — Prefill (run in the SIDEBAR, same window)")
    prefill_prompt = f"""Open {APP_URL} if it isn't already the active tab, go to the "🏠 Property & Cover" tab.
Read the structured property details from the main chat conversation in this window (the Extract prompt output).
Fill every matching field in the Property & Cover tab with those values. Fields auto-save — there is no save button.
For the property address, type the full format including state and postcode (e.g. "75 Bridge St, Lane Cove NSW 2066").
Leave any [unknown] values for me to complete, and tell me which ones they were when you finish."""
    st.code(prefill_prompt, language=None)

    st.subheader("Prompt 3 — Quote (run in the SIDEBAR)")
    sel_now = [b for b in ALL_INSURERS if st.session_state.get(f"sel_{b}")]
    sel_txt = ", ".join(sel_now) if sel_now else "[select insurers on the Instructions tab]"
    quote_prompt = f"""Read the property, tenancy, cover and policyholder details from the "🏠 Property & Cover" tab of this app ({APP_URL}). Then get landlord insurance quotes from: {sel_txt}.

Rules:
- Open each insurer's landlord insurance quote page in a NEW tab. Never navigate away from the app tab.
- Always select ANNUAL payment basis.
- Match the cover details exactly: cover type, sums insured, rent default option, flood, excess as close as possible to the preferred excess.
- Use the full address format with state and postcode for address lookups.
- PAUSE and ask me before submitting any form that finalises a quote or sends personal data. Do not buy anything.
- Known quirks: Budget Direct, Youi and NRMA need "always allow" permission grants before automation proceeds — ask me to click them. NRMA opens a new tab and needs "Continue without logging in" first. Youi requires a mobile PIN mid-quote and gives final pricing by phone call, not on screen. AAMI and GIO run on the same platform, so their flows are identical.
- When each quote completes, give me the result on ONE line in exactly this format:

Insurer: [name] | Annual: $[amount] | Monthly: $[amount] | Excess: $[amount] | Ref: [quote number] | Rent default: [yes/no] | Flood: [yes/no] | Notes: [discounts, restrictions]

I'll paste those lines into the Enter Quotes tab."""
    st.caption("Quote prompt — auto-updates with your insurer selection (copy button top-right)")
    st.code(quote_prompt, language=None)

# ===========================================================================
# TAB 4 — ENTER QUOTES
# ===========================================================================
with tab_enter:
    st.subheader("Quick Add — paste a results line")
    st.caption(
        "Format: Insurer: GIO | Annual: $1,234.56 | Monthly: $110.00 | Excess: $500 | "
        "Ref: Q123 | Rent default: yes | Flood: yes | Notes: online discount"
    )
    st.text_area("Paste one or more result lines", key="paste_results", height=120)

    def _parse_line(line):
        def grab(field, cast=str):
            m = re.search(rf"{field}\s*:\s*([^|]+)", line, re.IGNORECASE)
            if not m:
                return None
            raw = m.group(1).strip()
            if cast is float:
                raw = raw.replace("$", "").replace(",", "")
                try:
                    return float(raw)
                except ValueError:
                    return None
            return raw

        insurer = grab("Insurer")
        if not insurer:
            return None
        return {
            "insurer": insurer,
            "annual_premium": grab("Annual", float),
            "monthly_premium": grab("Monthly", float),
            "excess": grab("Excess", float),
            "ref": grab("Ref") or "",
            "rent_default": (grab("Rent default") or "").lower().startswith("y"),
            "flood": (grab("Flood") or "").lower().startswith("y"),
            "notes": grab("Notes") or "",
        }

    if st.button("Parse & add", key="parse_add"):
        added = 0
        for line in (_get("paste_results") or "").splitlines():
            if not line.strip():
                continue
            q = _parse_line(line)
            if q:
                st.session_state.quotes = [
                    x for x in st.session_state.quotes if x["insurer"] != q["insurer"]
                ] + [q]
                added += 1
        if added:
            st.success(f"Added/updated {added} quote(s).")
        else:
            st.warning("Couldn't parse anything — check the line format.")

    st.divider()
    st.subheader("Manual entry")
    with st.expander("Add a quote manually"):
        c1, c2, c3, c4 = st.columns(4)
        m_ins = c1.selectbox("Insurer", ALL_INSURERS, key="man_ins")
        m_ann = c2.number_input("Annual premium ($)", min_value=0.0, step=10.0, key="man_ann")
        m_mon = c3.number_input("Monthly premium ($)", min_value=0.0, step=1.0, key="man_mon")
        m_exc = c4.number_input("Excess ($)", min_value=0.0, step=50.0, key="man_exc")
        c1, c2, c3, c4 = st.columns(4)
        m_ref = c1.text_input("Quote ref", key="man_ref")
        m_rd = c2.selectbox("Rent default incl.", ["yes", "no"], key="man_rd")
        m_fl = c3.selectbox("Flood incl.", ["yes", "no"], key="man_fl")
        m_notes = c4.text_input("Notes", key="man_notes")
        if st.button("Add quote", key="man_add"):
            st.session_state.quotes = [
                x for x in st.session_state.quotes if x["insurer"] != m_ins
            ] + [{
                "insurer": m_ins, "annual_premium": m_ann or None,
                "monthly_premium": m_mon or None, "excess": m_exc or None,
                "ref": m_ref, "rent_default": m_rd == "yes",
                "flood": m_fl == "yes", "notes": m_notes,
            }]
            st.success(f"Added {m_ins}.")

    if st.session_state.quotes:
        st.divider()
        st.subheader(f"Quotes entered ({len(st.session_state.quotes)})")
        for q in sorted(st.session_state.quotes,
                        key=lambda x: x["annual_premium"] or 9e9):
            c1, c2 = st.columns([5, 1])
            c1.markdown(
                f"**{q['insurer']}** — {_money(q['annual_premium'])}/yr · "
                f"excess {_money(q['excess'])} · ref {q['ref'] or '—'}"
            )
            if c2.button("Remove", key=f"rm_{q['insurer']}"):
                st.session_state.quotes = [
                    x for x in st.session_state.quotes if x["insurer"] != q["insurer"]
                ]
                st.rerun()

# ===========================================================================
# TAB 5 — COMPARE
# ===========================================================================
with tab_compare:
    quotes = st.session_state.quotes
    renewal = float(_get("cur_renewal_premium") or 0)

    if not quotes:
        st.info("No quotes yet — add them in the Enter Quotes tab.")
    else:
        priced = [q for q in quotes if q["annual_premium"]]
        if priced:
            cheapest = min(priced, key=lambda q: q["annual_premium"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Cheapest quote",
                      _money(cheapest["annual_premium"]),
                      cheapest["insurer"])
            if renewal > 0:
                saving = renewal - cheapest["annual_premium"]
                c2.metric("Renewal baseline", _money(renewal),
                          _get("cur_insurer") or "current insurer")
                c3.metric("Saving vs renewal", _money(saving),
                          f"{saving / renewal * 100:.1f}%" if renewal else None)

        st.subheader("Side by side")
        cols = st.columns(min(len(quotes), 4))
        for i, q in enumerate(sorted(quotes, key=lambda x: x["annual_premium"] or 9e9)):
            with cols[i % len(cols)]:
                delta = ""
                if renewal > 0 and q["annual_premium"]:
                    d = renewal - q["annual_premium"]
                    arrow = "🟢" if d >= 0 else "🔴"
                    delta = f"\n\n{arrow} {_money(abs(d))} {'below' if d >= 0 else 'above'} renewal"
                card = (
                    f"### {q['insurer']}\n"
                    f"**{_money(q['annual_premium'])}** / year\n\n"
                    f"Monthly: {_money(q['monthly_premium'])}\n\n"
                    f"Excess: {_money(q['excess'])}\n\n"
                    f"Rent default: {'✅' if q['rent_default'] else '❌'} · "
                    f"Flood: {'✅' if q['flood'] else '❌'}\n\n"
                    f"Ref: `{q['ref'] or '—'}`{delta}"
                )
                if q["notes"]:
                    card += f"\n\n_{q['notes']}_"
                st.markdown(card)

        st.subheader("Full comparison table")
        rows = []
        if renewal > 0:
            rows.append({
                "Insurer": f"{_get('cur_insurer') or 'Current'} (renewal)",
                "Annual": renewal, "Monthly": None,
                "Excess": float(_get("cur_renewal_excess") or 0) or None,
                "Rent default": "—", "Flood": "—", "Ref": "—",
                "Saving vs renewal": 0.0, "Notes": "baseline",
            })
        for q in quotes:
            rows.append({
                "Insurer": q["insurer"],
                "Annual": q["annual_premium"],
                "Monthly": q["monthly_premium"],
                "Excess": q["excess"],
                "Rent default": "Yes" if q["rent_default"] else "No",
                "Flood": "Yes" if q["flood"] else "No",
                "Ref": q["ref"] or "—",
                "Saving vs renewal": (renewal - q["annual_premium"])
                if (renewal > 0 and q["annual_premium"]) else None,
                "Notes": q["notes"],
            })
        df = pd.DataFrame(rows).sort_values(
            "Annual", na_position="last"
        ).reset_index(drop=True)
        st.dataframe(
            df,
            width="stretch",
            column_config={
                "Annual": st.column_config.NumberColumn(format="$%.2f"),
                "Monthly": st.column_config.NumberColumn(format="$%.2f"),
                "Excess": st.column_config.NumberColumn(format="$%.0f"),
                "Saving vs renewal": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

        st.download_button(
            "⬇️ Download comparison (CSV)",
            df.to_csv(index=False).encode(),
            file_name="landlord_quote_comparison.csv",
            mime="text/csv",
        )
