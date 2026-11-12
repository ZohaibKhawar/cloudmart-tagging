"""Write the Week 9 short report (Word) from data/original.csv and data/remediated.csv.

Run from anywhere:  python report/build_report.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import cloudmart as cm  # noqa: E402

BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#1f1f1f", "#6b6a66"
OUT_DOCX = ROOT.parent / "Week 9 Activity - Resource Tagging Report.docx"
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

before = pd.read_csv(ROOT / "data" / "original.csv", dtype={"AccountID": str})
after = pd.read_csv(ROOT / "data" / "remediated.csv", dtype={"AccountID": str})
raw, notes = cm.load_raw(ROOT / "data" / "cloudmart_multi_account.csv")
log = pd.read_csv(ROOT / "data" / "remediation_log.csv")
sb, sa = cm.summary(before), cm.summary(after)
M = "(missing)"
money = lambda v: f"${v:,.0f}"

b = before.assign(Department=before["Department"].fillna(M), Environment=before["Environment"].fillna(M))
dept = b.pivot_table(index="Department", columns="Tagged", values="MonthlyCostUSD", aggfunc="sum", fill_value=0)
dept = dept.rename(columns={"Yes": "Tagged", "No": "Untagged"})
named_order = dept.drop(index=M).assign(t=lambda d: d.sum(axis=1)).sort_values("t", ascending=False).index.tolist()
dept = dept.loc[named_order + [M]]
env = b.groupby("Environment").agg(Resources=("ResourceID", "count"), Cost=("MonthlyCostUSD", "sum"),
                                   Tagged=("Tagged", lambda x: (x == "Yes").sum()))
env = env.loc[["Prod", "Dev", "Test", M]]
alloc = pd.DataFrame({
    "before": before[before["Tagged"] == "Yes"].groupby("Department")["MonthlyCostUSD"].sum(),
    "after": after.groupby("Department")["MonthlyCostUSD"].sum(),
}).fillna(0).sort_values("after", ascending=False)

# ------------------------------------------------------------------ figures
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": "#c9c8c3",
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})


def clean_axes(ax):
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


fig, ax = plt.subplots(figsize=(6.4, 2.45), dpi=200)
x = range(len(dept))
w = 0.38
ax.bar([i - w / 2 - 0.01 for i in x], dept["Tagged"], w, color=BLUE, label="Tagged")
ax.bar([i + w / 2 + 0.01 for i in x], dept["Untagged"], w, color=ORANGE, label="Untagged")
for i, v in enumerate(dept["Untagged"]):
    ax.text(i + w / 2 + 0.01, v + 12, f"${v:,.0f}", ha="center", fontsize=7, color=INK)
ax.set_xticks(list(x), [d if d != M else "no department" for d in dept.index])
ax.set_ylabel("Monthly cost (USD)")
ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
clean_axes(ax)
ax.legend(frameon=False, ncol=2, loc="upper right")
ax.set_title("Monthly cost per department by tagging status", loc="left", fontsize=10, color=INK)
fig.tight_layout()
fig.savefig(FIG / "dept_cost.png")
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.3), dpi=200, gridspec_kw={"width_ratios": [1.25, 1]})
ax = axes[0]
eb = b.groupby(["Environment", "Tagged"])["MonthlyCostUSD"].sum().unstack(fill_value=0).loc[env.index]
eb = eb.rename(columns={"Yes": "Tagged", "No": "Untagged"})
ax.bar(range(len(eb)), eb.get("Tagged", 0), 0.55, color=BLUE, label="Tagged")
ax.bar(range(len(eb)), eb.get("Untagged", 0), 0.55, bottom=eb.get("Tagged", 0), color=ORANGE, label="Untagged")
ax.set_xticks(range(len(eb)), [e if e != M else "missing" for e in eb.index])
ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
ax.set_title("Cost by environment", loc="left", fontsize=10, color=INK)
clean_axes(ax)
ax.legend(frameon=False, fontsize=8)
ax = axes[1]
stages = ["Before", "After"]
tag = [sb["tagged_cost"], sa["tagged_cost"]]
unt = [sb["untagged_cost"], sa["untagged_cost"]]
ax.bar(stages, tag, 0.5, color=BLUE)
ax.bar(stages, unt, 0.5, bottom=tag, color=ORANGE)
ax.text(0, sb["tagged_cost"] / 2, f"{sb['visibility_pct']:.1f}%\nallocated", ha="center", va="center",
        color="white", fontsize=8)
ax.text(1, sa["tagged_cost"] / 2, f"{sa['visibility_pct']:.0f}%\nallocated", ha="center", va="center",
        color="white", fontsize=8)
ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
ax.set_title("Remediation: before vs after", loc="left", fontsize=10, color=INK)
clean_axes(ax)
fig.tight_layout()
fig.savefig(FIG / "env_and_remediation.png")
plt.close(fig)

# ------------------------------------------------------------------ document
doc = Document()
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Inches(0.9)
sec.top_margin = sec.bottom_margin = Inches(0.8)
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
st.paragraph_format.space_after = Pt(4)
for name, size in [("Heading 1", 14), ("Heading 2", 12)]:
    hs = doc.styles[name]
    hs.font.name = "Calibri"
    hs.font.size = Pt(size)
    hs.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    hs.paragraph_format.space_before = Pt(10)
    hs.paragraph_format.space_after = Pt(4)


def p(text="", bold_lead=None, size=None, after=None, italic=False, align=None):
    para = doc.add_paragraph()
    if bold_lead:
        r = para.add_run(bold_lead + " ")
        r.bold = True
        if size:
            r.font.size = Pt(size)
    r = para.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if after is not None:
        para.paragraph_format.space_after = Pt(after)
    if align:
        para.alignment = align
    return para


def bullet(text, bold_lead=None, style="List Bullet"):
    para = doc.add_paragraph(style=style)
    if bold_lead:
        para.add_run(bold_lead + " ").bold = True
    para.add_run(text)
    para.paragraph_format.space_after = Pt(2)
    return para


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(rows, header, widths=None, size=9.5, right=()):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        shade(c, "DCE6F2")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            para = cells[i].paragraphs[0]
            run = para.add_run(str(v))
            run.font.size = Pt(size)
            if i in right:
                para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if widths:
        for row in t.rows:
            for i, wdt in enumerate(widths):
                row.cells[i].width = Inches(wdt)
    for row in t.rows[:-1]:  # keep each table on one page
        for c in row.cells:
            for para in c.paragraphs:
                para.paragraph_format.keep_with_next = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


title = doc.add_paragraph()
r = title.add_run("Week 9 Activity: Resource Tagging Based Cost Governance")
r.bold = True
r.font.size = Pt(17)
r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
title.paragraph_format.space_after = Pt(2)
p("Short report on the CloudMart Inc. resource tagging dataset", size=11, after=2, italic=True)
p("Name: ______________________     Student ID: ______________     Date: November 12, 2026", size=10, after=10)

doc.add_heading("1. Summary", level=1)
named = dept.drop(index=M)["Untagged"].sort_values(ascending=False)
table([
    ["% of untagged resources", f"{sb['untagged_pct']:.1f}%  ({sb['untagged']} of {sb['resources']} resources)"],
    ["Total untagged cost", f"{money(sb['untagged_cost'])} a month ({sb['untagged_cost_pct']:.1f}% of the "
                            f"{money(sb['total_cost'])} bill), about {money(sb['untagged_cost'] * 12)} a year"],
    ["Departments with missing tags",
     "All six: " + ", ".join(f"{d} {money(v)}" for d, v in named.items())
     + f", plus {money(dept.loc[M, 'Untagged'])} with no department at all (ec2-004 and ebs-002)"],
    ["Most missing tag", f"Owner, missing on all {sb['untagged']} untagged resources"],
    ["Where untagged resources are", "Every Dev (14) and Test (3) resource; no Prod resource. "
                                     "18 of the 19 were created manually."],
    ["After remediation", f"Cost visibility {sb['visibility_pct']:.1f}% to {sa['visibility_pct']:.0f}%; "
                          f"untagged cost {money(sb['untagged_cost'])} to {money(sa['untagged_cost'])}"],
], ["Measure", "Result"], widths=[1.9, 4.8])

doc.add_heading("2. Data and method", level=1)
p(f"The dataset (cloudmart_multi_account.csv) lists CloudMart's resources across six linked AWS accounts, "
  f"one per department, with their tags and monthly cost. Three problems had to be fixed before analysis:")
bullet("every line is wrapped in quotes, so a plain pd.read_csv() reads a single column; the quotes were "
       "stripped and each line split again;", "Quoted rows:")
bullet("ebs-002 and ec2-004 are two fields short, which would shift Manual into Owner and the cost into "
       "CostCenter; the last three values (CreatedBy, MonthlyCostUSD, Tagged) were kept at the end and the "
       "missing tags left blank;", "Short rows:")
bullet(f"rows 38 to 73 repeat rows 2 to 37, so {notes['rows_read']} rows hold {sb['resources']} resources. "
       "The duplicates were removed (percentages are unchanged; dollar totals would otherwise double).",
       "Duplicates:")
p("The analysis is in eda.ipynb (pandas and Plotly). The Streamlit dashboard (app.py) shows the same "
  "results with Service, Region, Department and Environment filters, and an editable remediation table. "
  "A resource counts as tagged when Department, Project, Environment, Owner and CostCenter are all filled in; "
  "this rule reproduces the dataset's own Tagged column exactly.")

doc.add_heading("3. Findings", level=1)
p(f"CloudMart spends {money(sb['total_cost'])} a month. Only {money(sb['tagged_cost'])} "
  f"({sb['visibility_pct']:.1f}%) sits on fully tagged resources; {money(sb['untagged_cost'])} "
  f"({sb['untagged_cost_pct']:.1f}%) cannot be charged back to a team with a named owner.")
bullet("Sales has the most untagged cost among named departments ($240), and $440 once ec2-004 "
       "($200, in Sales' account 1002) is counted. Every department has some.", "Departments:")
bullet("CRMTool (Sales) is the largest project at $960 a month (26% of spend), then LedgerDB at $355.",
       "Projects:")
bullet("Owner is missing on 19 resources; Department, Project, Environment and CostCenter on 2 each. "
       "17 resources score 6/6 on the Tag Completeness Score, 17 score 5/6 and 2 score 1/6.", "Tags:")
bullet("Prod (17 resources, $2,340) is 100% tagged; Dev (14, $1,000) and Test (3, $125) are 0% tagged.",
       "Environments:")
bullet("18 of 19 untagged resources were created manually; 17 of the 18 created by Terraform, Jenkins or "
       "CloudFormation are tagged.", "Provisioning:")
doc.add_picture(str(FIG / "dept_cost.png"), width=Inches(6.0))
p("Figure 1. Monthly cost per department, tagged (blue) and untagged (orange).", size=9, italic=True, after=8)
doc.add_picture(str(FIG / "env_and_remediation.png"), width=Inches(6.0))
p("Figure 2. Left: untagged cost is all non-production. Right: allocated (blue) and hidden (orange) cost "
  "before and after remediation.", size=9, italic=True, after=8)

doc.add_heading("4. Remediation (before and after)", level=1)
conf = log[log["NeedsOwnerConfirmation"] == "Yes"]
p(f"{len(log)} tag values were filled on {log['ResourceID'].nunique()} resources using only what the tagged "
  "resources already show: Department and CostCenter from the AccountID, Owner from the department's "
  "named owner, and, for the two bare resources, Project and Environment from their Prod twin in the same "
  f"account, service and region. The {len(conf)} values from the last rule are flagged for the owner to "
  "confirm. In the dashboard the same edits can be made by hand in st.data_editor and downloaded with "
  "st.download_button.")
table([
    ["Untagged resources", f"{sb['untagged']} ({sb['untagged_pct']:.1f}%)", f"{sa['untagged']} (0%)"],
    ["Untagged monthly cost", money(sb["untagged_cost"]), money(sa["untagged_cost"])],
    ["Cost visibility", f"{sb['visibility_pct']:.1f}%", f"{sa['visibility_pct']:.0f}%"],
    ["Cost with no department", money(before.loc[before["Department"].isna(), "MonthlyCostUSD"].sum()),
     money(after.loc[after["Department"].isna(), "MonthlyCostUSD"].sum())],
    ["Resources with an owner", str(before["Owner"].notna().sum()), str(after["Owner"].notna().sum())],
], ["Measure", "Before", "After"], widths=[2.6, 2.0, 2.0], right=(1, 2))
table([[d, money(r.before), money(r.after), "+" + money(r.after - r.before)] for d, r in alloc.iterrows()],
      ["Department", "Allocated before", "Allocated after", "Newly visible"],
      widths=[1.8, 1.6, 1.6, 1.6], right=(1, 2, 3))

doc.add_heading("5. Recommendations for governance", level=1)
recs = [
    ("Make five tags mandatory", "(Department, Project, Environment, Owner, CostCenter) and enforce them with "
     "AWS Organizations tag policies plus an SCP that denies creating resources without them."),
    ("Provision through IaC.", "Use Terraform default_tags and CloudFormation stack tags; every tagged "
     "resource here came from Terraform, Jenkins or CloudFormation. Limit manual console creation in Dev and Test."),
    ("Require Owner as an email address.", "It was the tag most often missing and the one budgets, alerts and "
     "incident response need."),
    ("Activate them as cost allocation tags", "so Cost Explorer, the Cost and Usage Report and AWS Budgets can "
     "group by department and project; send each department a monthly showback."),
    ("Run a weekly compliance report", "(the dashboard's untagged list) to each owner, with a target of 95%+ "
     "cost visibility, and stop untagged Dev/Test resources automatically after a grace period."),
    ("Keep one linked account per department", "as a backstop: it is how ec2-004 and ebs-002 could still be "
     "traced to Sales and Marketing."),
]
for lead, text in recs:
    bullet(text, lead, style="List Number")

doc.add_heading("6. Reflection (Task 5.5)", level=1)
p("Before remediation more than a third of the bill could not be charged to anyone. Owner was missing on "
  "every untagged resource, so there was no person to ask about the spend or to alert when it grew, and $245 "
  "could not be placed in any department's showback. The gaps followed a clear pattern: production built "
  "with infrastructure as code was tagged, while Dev and Test resources created by hand were not. Once the "
  "tags were filled in, every dollar lands on a department, project, cost center and owner, so chargeback "
  "reports add up to the full bill, each team sees its own non-production spend and can shut idle "
  "environments down, and budgets reach a real person. Remediation fixes the past; enforcing tags at "
  "creation time is what keeps the reports accurate.")

doc.add_heading("Deliverables", level=2)
for f, d in [
    ("eda.ipynb / eda.html", "EDA notebook with outputs; app.py: Streamlit dashboard (streamlit run app.py)"),
    ("data/original.csv and data/remediated.csv", "before and after datasets (36 resources each)"),
    ("data/untagged.csv, data/remediation_log.csv", "Task 3.5 export and the list of every tag filled"),
]:
    bullet(d, f + ":")

doc.save(OUT_DOCX)
print("wrote", OUT_DOCX)
