# CloudMart tagging and cost governance (Week 9 activity)

Exploratory analysis and a Streamlit dashboard for the CloudMart resource tagging dataset:
how many resources are untagged, how much cost that hides, and what tag remediation recovers.

## Run the dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501. Pressing Run on `app.py` in VS Code also works: the script
relaunches itself through `streamlit run`.

Tabs follow the activity sheet: 1 Explore, 2 Cost visibility, 3 Compliance, 4 Charts,
5 Remediation, Report. The sidebar has the Service, Region, Department and Environment filters
(Task 4.5) and an upload box for another CloudMart CSV (for example `data/remediated.csv`).

In **5 Remediation** the untagged resources are an editable table (`st.data_editor`). Type or pick
the missing Department, Project, Environment, Owner and CostCenter, or press **Fill suggested tags**,
then compare the before/after numbers and download `remediated.csv`.

## Files

| File | What it is |
|---|---|
| `eda.ipynb` / `eda.html` | EDA notebook, Task Sets 1 to 5, with outputs |
| `app.py` | Streamlit dashboard |
| `cloudmart.py` | Loading, cleaning, completeness score and tag suggestion helpers used by the app |
| `data/cloudmart_multi_account.csv` | The dataset as provided |
| `data/original.csv` | Before: cleaned dataset, 36 resources |
| `data/remediated.csv` | After: the same resources with the missing tags filled in |
| `data/untagged.csv` | Task 3.5 export (19 untagged resources) |
| `data/remediation_log.csv` | Every tag value filled, with the rule used |
| `report/build_report.py` | Writes the short Word report from the CSVs |

## Data notes

The provided CSV needs three fixes before analysis (done in both the notebook and `cloudmart.py`):

1. Every line is wrapped in quotes, so a plain `pd.read_csv()` reads a single column.
2. `ebs-002` and `ec2-004` are two fields short; the last three values (CreatedBy, MonthlyCostUSD,
   Tagged) are kept at the end and the missing tags left blank.
3. Rows 38 to 73 repeat rows 2 to 37, so 72 rows hold 36 resources; the duplicates are removed.

## Key results

- 19 of 36 resources untagged (52.8%)
- $1,370 of $3,710 a month untagged (36.9%)
- Untagged cost by department: Sales $240, Analytics $210, Finance $200, HR $170, DevOps $165,
  Marketing $140, plus $245 with no department
- Owner is the most missing tag; every Dev and Test resource is untagged, every Prod resource tagged
- After remediation: cost visibility 63.1% to 100%

## Hosting it (optional)

To get a public dashboard link, push this folder to a GitHub repository and deploy `app.py` from
https://share.streamlit.io (sign in with GitHub, New app, pick the repo and `app.py`).
