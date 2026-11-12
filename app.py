"""CloudMart tagging governance dashboard (Week 9 activity).

Run:  streamlit run app.py      (or press Run in VS Code: it relaunches itself)
"""
from pathlib import Path

import streamlit as st

# Started with plain "python app.py" (VS Code's Run button)?
# Relaunch through "streamlit run" so the app actually opens in the browser.
if __name__ == "__main__" and not st.runtime.exists():
    import sys
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__).resolve())]
    sys.exit(stcli.main())

import pandas as pd
import plotly.express as px

import cloudmart as cm

HERE = Path(__file__).resolve().parent
RAW_PATH = HERE / "data" / "cloudmart_multi_account.csv"
COLORS = {"Tagged": "#2a78d6", "Untagged": "#eb6834"}
EDIT_COLS = ["ResourceID", "AccountID", "Service", "Region", "MonthlyCostUSD",
             "Department", "Project", "Environment", "Owner", "CostCenter"]
EDITABLE = ["Department", "Project", "Environment", "Owner", "CostCenter"]
M = cm.MISSING_LABEL

st.set_page_config(page_title="CloudMart Tagging Governance", page_icon="🏷️", layout="wide")
try:  # gap colour between bar segments = the page background
    SURFACE = "#0e1117" if st.context.theme.type == "dark" else "#ffffff"
except Exception:
    SURFACE = "#ffffff"


def money(v: float) -> str:
    return f"${v:,.0f}"


def md(text: str) -> None:
    """st.markdown, with $ escaped so Streamlit doesn't read "$240 ... $210" as LaTeX."""
    st.markdown(text.replace("$", r"\$"))


def style(fig, **kw):
    fig.update_layout(font_family="Segoe UI, Arial", barcornerradius=4, legend_title_text="",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                      margin=dict(l=10, r=10, t=70, b=10), hoverlabel_namelength=-1, **kw)
    return fig


def with_status(d: pd.DataFrame) -> pd.DataFrame:
    return d.assign(Status=d["Tagged"].map({"Yes": "Tagged", "No": "Untagged"}),
                    Department=d["Department"].fillna(M),
                    Environment=d["Environment"].fillna(M))


# ---------------------------------------------------------------- data
st.sidebar.header("Data")
upload = st.sidebar.file_uploader("Use another CloudMart CSV (optional)", type="csv")
if upload is not None:
    df, notes = cm.load(upload)
    source_sig = f"{upload.name}:{upload.size}"
    source_name = upload.name
else:
    df, notes = cm.load(RAW_PATH)
    source_sig = "default"
    source_name = RAW_PATH.name
df["TagCompleteness"] = cm.completeness(df)

st.sidebar.caption(
    f"**{source_name}**: {notes['rows_read']} rows read, {notes['short_rows_fixed']} short rows "
    f"re-aligned, {notes['duplicate_rows']} exact duplicates removed, leaving **{len(df)} resources**."
)

# ---------------------------------------------------------------- filters (4.5)
st.sidebar.header("Filters")
st.sidebar.caption("Leave a filter empty to include everything.")


def pick(label, col):
    opts = sorted(df[col].fillna(M).unique().tolist())
    return st.sidebar.multiselect(label, opts, placeholder="All")


f_service = pick("Service", "Service")
f_region = pick("Region", "Region")
f_dept = pick("Department", "Department")
f_env = pick("Environment", "Environment")

mask = pd.Series(True, index=df.index)
for col, chosen in [("Service", f_service), ("Region", f_region),
                    ("Department", f_dept), ("Environment", f_env)]:
    if chosen:
        mask &= df[col].fillna(M).isin(chosen)
view = df[mask]

# ---------------------------------------------------------------- header + KPIs
st.title("CloudMart tagging and cost governance")
st.caption("Week 9 activity: how missing tags hide cloud cost, and what remediation recovers.")
if view.empty:
    st.warning("No resources match these filters.")
    st.stop()

s = cm.summary(view)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Resources", s["resources"], help="After removing duplicate rows", border=True)
k2.metric("Untagged resources", s["untagged"], f"{s['untagged_pct']:.1f}% of resources",
          delta_color="off", delta_arrow="off", border=True)
k3.metric("Monthly cost", money(s["total_cost"]), border=True)
k4.metric("Untagged cost", money(s["untagged_cost"]), f"{s['untagged_cost_pct']:.1f}% of cost",
          delta_color="off", delta_arrow="off", border=True)
if mask.sum() < len(df):
    st.caption(f"Filtered: {mask.sum()} of {len(df)} resources.")

t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Explore", "2 · Cost visibility", "3 · Compliance",
                                  "4 · Charts", "5 · Remediation", "Report"])

# ---------------------------------------------------------------- Task Set 1
with t1:
    st.subheader("1.1 First 5 rows")
    st.dataframe(view.drop(columns="TagCompleteness").head(5), hide_index=True)
    with st.expander("Why the file needs cleaning before it loads"):
        md(
            "- Every line of the CSV is wrapped in quotes, so a plain `pd.read_csv()` reads one column. "
            "The quotes are stripped and each line split again.\n"
            "- `ebs-002` and `ec2-004` are two fields short (`...,us-west-1,,,,Manual,45,No`). The last "
            "three values (CreatedBy, MonthlyCostUSD, Tagged) are kept at the end and the missing tags left blank.\n"
            f"- Rows 38 to 73 repeat rows 2 to 37 exactly, so {notes['duplicate_rows']} duplicate rows are "
            "dropped. Percentages are the same either way; dollar totals would double."
        )
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1.2 / 1.3 Missing values")
        miss = view.drop(columns="TagCompleteness").isnull().sum()
        miss_df = pd.DataFrame({"Missing": miss, "% of resources": (miss / len(view) * 100).round(1)})
        st.dataframe(miss_df.sort_values("Missing", ascending=False))
        top = miss.sort_values(ascending=False)
        if top.iloc[0] > 0:
            md(f"Most missing: **{top.index[0]}** ({top.iloc[0]} of {len(view)} resources).")
    with c2:
        st.subheader("1.4 / 1.5 Tagged vs untagged")
        vc = view["Tagged"].value_counts().reindex(["Yes", "No"], fill_value=0)
        st.dataframe(vc.rename("Resources").to_frame())
        md(f"**{s['untagged_pct']:.1f}%** of resources are untagged "
                    f"({s['untagged']} of {s['resources']}).")

# ---------------------------------------------------------------- Task Set 2
with t2:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("2.1 / 2.2 Cost of tagged vs untagged")
        st.dataframe(pd.DataFrame({
            "Monthly cost (USD)": [s["tagged_cost"], s["untagged_cost"], s["total_cost"]],
            "% of cost": [100 - s["untagged_cost_pct"], s["untagged_cost_pct"], 100.0],
        }, index=["Tagged", "Untagged", "Total"]).round(1))
        md(f"**{s['untagged_cost_pct']:.1f}%** of spend ({money(s['untagged_cost'])} a month) "
                    "is on untagged resources.")
    with c2:
        st.subheader("2.3 Untagged cost by department")
        vs = with_status(view)
        dept = vs.pivot_table(index="Department", columns="Status", values="MonthlyCostUSD",
                              aggfunc="sum", fill_value=0)
        for c in ["Tagged", "Untagged"]:
            if c not in dept:
                dept[c] = 0.0
        dept = dept[["Tagged", "Untagged"]].sort_values("Untagged", ascending=False)
        st.dataframe(dept)
        named = dept.drop(index=M, errors="ignore")
        if not named.empty and named["Untagged"].max() > 0:
            md(f"Named department with the most untagged cost: **{named['Untagged'].idxmax()}** "
                        f"({money(named['Untagged'].max())}).")
        if M in dept.index and dept.loc[M, "Untagged"] > 0:
            md(f"{money(dept.loc[M, 'Untagged'])} has **no department at all**. By AccountID it "
                        "belongs to Sales (`ec2-004`, $200) and Marketing (`ebs-002`, $45).")
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("2.4 Cost by project")
        proj = view.assign(Project=view["Project"].fillna(M)).groupby("Project")["MonthlyCostUSD"].sum()
        proj = proj.sort_values(ascending=False)
        st.dataframe(proj.rename("Monthly cost (USD)").to_frame())
        md(f"Top project: **{proj.index[0]}** ({money(proj.iloc[0])}, "
                    f"{proj.iloc[0] / proj.sum() * 100:.0f}% of spend).")
    with c4:
        st.subheader("2.5 Prod vs Dev (and Test)")
        env = vs.groupby("Environment").agg(
            Resources=("ResourceID", "count"),
            Cost=("MonthlyCostUSD", "sum"),
            Tagged=("Tagged", lambda x: (x == "Yes").sum()),
        )
        env["% tagged"] = (env["Tagged"] / env["Resources"] * 100).round(0)
        st.dataframe(env.sort_values("Cost", ascending=False))
        md("Prod is fully tagged; Dev and Test are not tagged at all. 18 of the 19 untagged "
                    "resources were created **Manually**; IaC-created resources are almost all tagged.")
        st.dataframe(pd.crosstab(view["CreatedBy"], view["Tagged"]))

# ---------------------------------------------------------------- Task Set 3
with t3:
    st.subheader("3.1 Tag Completeness Score (0 to 6)")
    st.caption("Counts how many of Department, Project, Environment, Owner, CostCenter and CreatedBy are filled in.")
    score_cols = ["ResourceID", "Service", "Department", "Environment", "Owner",
                  "MonthlyCostUSD", "Tagged", "TagCompleteness"]
    st.dataframe(
        view[score_cols].sort_values(["TagCompleteness", "MonthlyCostUSD"], ascending=[True, False]),
        hide_index=True, height=260,
        column_config={"TagCompleteness": st.column_config.ProgressColumn(
            "Completeness", min_value=0, max_value=len(cm.TAG_FIELDS), format="%d / 6"),
            "MonthlyCostUSD": st.column_config.NumberColumn("Monthly cost", format="$%d")},
    )
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("3.2 Five lowest scores")
        st.caption("Ties broken by cost, most expensive first.")
        st.dataframe(view.sort_values(["TagCompleteness", "MonthlyCostUSD"], ascending=[True, False])
                     [["ResourceID", "Service", "AccountID", "TagCompleteness", "MonthlyCostUSD"]].head(5),
                     hide_index=True)
    with c2:
        st.subheader("3.3 Missing tag fields")
        st.dataframe(view[cm.TAG_FIELDS].isnull().sum().sort_values(ascending=False).rename("Missing").to_frame())
    st.subheader("3.4 Untagged resources")
    unt = view[view["Tagged"] == "No"].sort_values("MonthlyCostUSD", ascending=False)
    st.dataframe(unt.drop(columns="TagCompleteness"), hide_index=True,
                 column_config={"MonthlyCostUSD": st.column_config.NumberColumn("Monthly cost", format="$%d")})
    md(f"**{len(unt)}** untagged resources costing **{money(unt['MonthlyCostUSD'].sum())}** a month.")
    st.download_button("3.5 Download untagged.csv", cm.to_csv_bytes(unt.drop(columns="TagCompleteness")),
                       "untagged.csv", "text/csv")

# ---------------------------------------------------------------- Task Set 4
with t4:
    vs = with_status(view)
    c1, c2 = st.columns(2)
    with c1:
        counts = vs["Status"].value_counts().reindex(["Tagged", "Untagged"], fill_value=0).reset_index()
        fig = px.pie(counts, names="Status", values="count", hole=0.5, color="Status",
                     color_discrete_map=COLORS, title="4.1 Resources by tagging status")
        fig.update_traces(textinfo="label+value+percent", sort=False, insidetextorientation="horizontal",
                          marker_line_color=SURFACE, marker_line_width=2,
                          hovertemplate="%{label}: %{value} resources (%{percent})<extra></extra>")
        st.plotly_chart(style(fig), width="stretch")
    with c2:
        d = vs.groupby(["Department", "Status"], as_index=False)["MonthlyCostUSD"].sum()
        dorder = vs.groupby("Department")["MonthlyCostUSD"].sum().drop(index=M, errors="ignore")
        dorder = dorder.sort_values(ascending=False).index.tolist() + [M]
        fig = px.bar(d, x="Department", y="MonthlyCostUSD", color="Status", barmode="group",
                     color_discrete_map=COLORS, title="4.2 Monthly cost per department by tagging status",
                     category_orders={"Status": ["Tagged", "Untagged"], "Department": dorder},
                     labels={"MonthlyCostUSD": "Monthly cost (USD)"})
        fig.update_traces(hovertemplate="%{x} · %{fullData.name}: $%{y:,.0f}<extra></extra>")
        st.plotly_chart(style(fig, bargap=0.25, bargroupgap=0.08), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        d = vs.groupby(["Service", "Status"], as_index=False)["MonthlyCostUSD"].sum()
        order = vs.groupby("Service")["MonthlyCostUSD"].sum().sort_values(ascending=False).index.tolist()
        fig = px.bar(d, y="Service", x="MonthlyCostUSD", color="Status", orientation="h",
                     color_discrete_map=COLORS, title="4.3 Total monthly cost per service",
                     category_orders={"Service": order, "Status": ["Tagged", "Untagged"]},
                     labels={"MonthlyCostUSD": "Monthly cost (USD)"})
        fig.update_traces(marker_line_color=SURFACE, marker_line_width=1,
                          hovertemplate="%{y} · %{fullData.name}: $%{x:,.0f}<extra></extra>")
        st.plotly_chart(style(fig), width="stretch")
    with c4:
        d = vs.groupby(["Environment", "Status"], as_index=False)["MonthlyCostUSD"].sum()
        fig = px.bar(d, x="Environment", y="MonthlyCostUSD", color="Status",
                     color_discrete_map=COLORS, title="4.4 Monthly cost by environment",
                     category_orders={"Environment": ["Prod", "Dev", "Test", M],
                                      "Status": ["Tagged", "Untagged"]},
                     labels={"MonthlyCostUSD": "Monthly cost (USD)"})
        fig.update_traces(marker_line_color=SURFACE, marker_line_width=1,
                          hovertemplate="%{x} · %{fullData.name}: $%{y:,.0f}<extra></extra>")
        st.plotly_chart(style(fig, bargap=0.35), width="stretch")
    st.caption("4.5 Use the Service, Region, Department and Environment filters in the sidebar; every chart redraws.")

# ---------------------------------------------------------------- Task Set 5
untagged0 = df[df["Tagged"] == "No"][EDIT_COLS].reset_index(drop=True)
ss = st.session_state
if ss.get("rem_sig") != source_sig:
    ss.rem_sig, ss.rem_base, ss.rem_ver = source_sig, untagged0.copy(), ss.get("rem_ver", 0) + 1

with t5:
    st.subheader("5.1 / 5.2 Fill in the missing tags")
    st.caption("Works on the full dataset (filters don't apply here). Edit the cells marked with a pencil, or let the "
               "suggestions fill them from the tagged resources, then check and change anything.")
    b1, b2, _ = st.columns([1.4, 1, 3])
    if b1.button("Fill suggested tags", type="primary"):
        suggested, _log = cm.suggest_tags(df)
        ss.rem_base = suggested[suggested["ResourceID"].isin(untagged0["ResourceID"])][EDIT_COLS].reset_index(drop=True)
        ss.rem_ver += 1
    if b2.button("Clear my edits"):
        ss.rem_base, ss.rem_ver = untagged0.copy(), ss.rem_ver + 1

    opt = lambda col: sorted(df[col].dropna().unique().tolist())
    edited = st.data_editor(
        ss.rem_base, key=f"rem_editor_{ss.rem_ver}", hide_index=True, num_rows="fixed",
        disabled=["ResourceID", "AccountID", "Service", "Region", "MonthlyCostUSD"],
        column_config={
            "MonthlyCostUSD": st.column_config.NumberColumn("Monthly cost", format="$%d"),
            "Department": st.column_config.SelectboxColumn(options=opt("Department")),
            "Project": st.column_config.SelectboxColumn(options=opt("Project")),
            "Environment": st.column_config.SelectboxColumn(options=["Prod", "Dev", "Test"]),
            "CostCenter": st.column_config.SelectboxColumn(options=opt("CostCenter")),
            "Owner": st.column_config.TextColumn(validate=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                                                 help="Owner's email address"),
        },
    )

    # Merge the edits back into the full dataset and recompute Tagged.
    after = df.drop(columns="TagCompleteness").copy()
    ed = edited.set_index("ResourceID")[EDITABLE].replace(r"^\s*$", pd.NA, regex=True)
    rows = after["ResourceID"].isin(ed.index)
    for col in EDITABLE:
        after.loc[rows, col] = ed.loc[after.loc[rows, "ResourceID"], col].to_numpy()
    after = cm.recompute_tagged(after)
    before = df.drop(columns="TagCompleteness")
    sb, sa = cm.summary(before), cm.summary(after)

    left = after[after["Tagged"] == "No"]
    if left.empty:
        st.success("All resources now carry Department, Project, Environment, Owner and CostCenter.")
    else:
        gaps = left.set_index("ResourceID")[cm.REQUIRED_TAGS].isna()
        st.info(f"{len(left)} resources still untagged. Missing: " + "; ".join(
            f"{rid} ({', '.join(gaps.columns[gaps.loc[rid]]) or 'Owner must be an email'})"
            for rid in gaps.index[:8]) + (" ..." if len(left) > 8 else ""))

    st.subheader("5.4 Cost visibility before and after")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Untagged resources", sa["untagged"], sa["untagged"] - sb["untagged"], delta_color="inverse")
    m2.metric("Untagged cost", money(sa["untagged_cost"]),
              f"{money(sa['untagged_cost'] - sb['untagged_cost'])}".replace("$-", "-$"), delta_color="inverse")
    m3.metric("Cost visibility", f"{sa['visibility_pct']:.1f}%",
              f"{sa['visibility_pct'] - sb['visibility_pct']:+.1f} pts")
    m4.metric("Resources with an owner", int(after["Owner"].notna().sum()),
              int(after["Owner"].notna().sum() - before["Owner"].notna().sum()))

    c1, c2 = st.columns([2, 3])
    with c1:
        cmp = pd.DataFrame({
            "Stage": ["Before", "Before", "After", "After"],
            "Status": ["Tagged", "Untagged"] * 2,
            "MonthlyCostUSD": [sb["tagged_cost"], sb["untagged_cost"], sa["tagged_cost"], sa["untagged_cost"]],
        })
        fig = px.bar(cmp, x="Stage", y="MonthlyCostUSD", color="Status", color_discrete_map=COLORS,
                     title="Allocated vs hidden monthly cost", labels={"MonthlyCostUSD": "Monthly cost (USD)"},
                     category_orders={"Status": ["Tagged", "Untagged"]})
        fig.update_traces(marker_line_color=SURFACE, marker_line_width=1,
                          hovertemplate="%{x} · %{fullData.name}: $%{y:,.0f}<extra></extra>")
        st.plotly_chart(style(fig, bargap=0.45), width="stretch")
    with c2:
        alloc = pd.DataFrame({
            "Allocated before": before[before["Tagged"] == "Yes"].groupby("Department")["MonthlyCostUSD"].sum(),
            "Allocated after": after[after["Tagged"] == "Yes"].groupby("Department")["MonthlyCostUSD"].sum(),
        }).fillna(0)
        alloc["Newly visible"] = alloc["Allocated after"] - alloc["Allocated before"]
        md("**Cost each department can now be charged for** (fully tagged resources only)")
        st.dataframe(alloc.sort_values("Allocated after", ascending=False),
                     column_config={c: st.column_config.NumberColumn(format="dollar") for c in alloc.columns})

    st.subheader("5.3 Download")
    changes = []
    base0 = untagged0.set_index("ResourceID")
    for rid in ed.index:
        for col in EDITABLE:
            old, new = base0.at[rid, col], ed.at[rid, col]
            if (pd.isna(old) and not pd.isna(new)) or (not pd.isna(old) and not pd.isna(new) and old != new):
                changes.append({"ResourceID": rid, "Field": col,
                                "Before": "" if pd.isna(old) else old, "After": new})
    d1, d2, _ = st.columns([2, 2, 3])
    d1.download_button("Download remediated.csv", cm.to_csv_bytes(after), "remediated.csv", "text/csv",
                       type="primary")
    d2.download_button("Download change log", cm.to_csv_bytes(pd.DataFrame(
        changes, columns=["ResourceID", "Field", "Before", "After"])), "remediation_changes.csv", "text/csv")
    st.caption(f"{len(changes)} tag value{'' if len(changes) == 1 else 's'} changed so far.")

# ---------------------------------------------------------------- report
with t6:
    vb = with_status(before)
    dept_unt = vb[vb["Status"] == "Untagged"].groupby("Department")["MonthlyCostUSD"].sum().sort_values(ascending=False)
    st.subheader("Summary")
    md(
        f"- **Untagged resources:** {sb['untagged']} of {sb['resources']} (**{sb['untagged_pct']:.1f}%**)\n"
        f"- **Total untagged cost:** **{money(sb['untagged_cost'])}** a month of {money(sb['total_cost'])} "
        f"({sb['untagged_cost_pct']:.1f}%), about {money(sb['untagged_cost'] * 12)} a year\n"
        "- **Departments with missing tags:** "
        + ", ".join(f"{d} {money(v)}" for d, v in dept_unt.drop(index=M, errors="ignore").items())
        + (f", plus {money(dept_unt[M])} with no department" if M in dept_unt.index else "") + "\n"
        "- **Most missing tag:** Owner, on every untagged resource\n"
        "- **Where it happens:** all Dev and Test resources; 18 of 19 untagged resources were created manually\n"
        f"- **After remediation (current edits):** cost visibility {sb['visibility_pct']:.1f}% → "
        f"{sa['visibility_pct']:.1f}%, untagged cost {money(sb['untagged_cost'])} → {money(sa['untagged_cost'])}"
    )
    st.subheader("Recommendations for governance")
    md(
        "1. **Make five tags mandatory** (Department, Project, Environment, Owner, CostCenter) and enforce "
        "them with AWS Organizations tag policies, plus an SCP that denies creating resources without them.\n"
        "2. **Provision through IaC only.** Terraform `default_tags` / CloudFormation stack tags; tagged "
        "resources here all came from Terraform, Jenkins or CloudFormation. Restrict manual console creation in Dev/Test.\n"
        "3. **Owner is an email, not a name.** It is the tag most often missing and the one budgets and "
        "alerts need.\n"
        "4. **Activate the tags as cost allocation tags** so Cost Explorer, CUR and AWS Budgets can group by them; "
        "run showback per department monthly.\n"
        "5. **Weekly compliance report** (this dashboard's untagged list) sent to each owner, with a target of "
        "95%+ cost visibility; auto-stop untagged Dev/Test resources after a grace period.\n"
        "6. **Use the account as a backstop:** linked accounts per department mean even an untagged resource "
        "can be traced to a department, as was done here for `ebs-002` and `ec2-004`."
    )
    st.subheader("5.5 Reflection")
    md(
        "Before remediation more than a third of the bill could not be charged to anyone: Owner was "
        "missing on every untagged resource, so there was no person to ask about the spend or alert when it "
        "grew, and $245 could not be placed in any department's showback at all. Tagging gaps followed a "
        "clear pattern: production built with IaC was tagged, and Dev/Test created by hand was not. After "
        "filling the tags every dollar lands on a department, project, cost center and owner, so "
        "chargeback reports add up to the full bill, teams see their own non-production spend and can "
        "shut idle environments down, and budgets reach a real person. Remediation fixes the past; "
        "enforcement at creation time keeps it fixed."
    )
