# SK-01 Capstone Project: Multi-Source HR Data Integration Pipeline

## 1. Pipeline Purpose and Business Context

GlobalTech Corp recently acquired AcquiredCo and needs a unified, trusted employee dataset for HR operations, payroll review, benefits analysis, workforce reporting, and post-merger integration planning.

The purpose of this pipeline is to ingest employee-related data from multiple HR, payroll, and benefits systems, standardize the schemas, clean and normalize key fields, resolve duplicate identities, validate data quality, and produce a golden employee dataset with supporting review artifacts.

The pipeline is designed around the following principles:

- HRIS systems are the source of truth for employee identity and core employee attributes.
- Payroll and benefits systems are enrichment sources, not identity systems.
- Exact employee ID matches are used for automatic integration.
- Fuzzy name matches are used only for HR review and are not automatically merged.
- Data quality issues are reported transparently rather than silently corrected.
- Final outputs are separated into trusted datasets and exception-review reports.

## 2. Input Sources

The pipeline reads raw source files from `data/raw/`.

### 2.1 GlobalTech HRIS

**Path:** `data/raw/globaltech_hris.csv`
**Format:** CSV
**Encoding:** UTF-8
**System role:** Primary HRIS identity source for GlobalTech employees

Expected source columns:

| Column            | Description                    |
| ----------------- | ------------------------------ |
| `employee_id`     | GlobalTech employee identifier |
| `first_name`      | Employee first name            |
| `last_name`       | Employee last name             |
| `email`           | Employee email address         |
| `department`      | Source department value        |
| `job_title`       | Employee job title             |
| `hire_date`       | Employee hire date             |
| `country`         | Employee country               |
| `employment_type` | Employment type                |
| `manager_id`      | Source manager employee ID     |
| `source_system`   | Source system label            |

### 2.2 AcquiredCo HRIS

**Path:** `data/raw/acquiredco_hris.json`
**Format:** JSON
**System role:** Primary HRIS identity source for AcquiredCo employees

The AcquiredCo source is ingested as a simulated paginated API response.

Expected source fields include:

| Field                       | Description                    |
| --------------------------- | ------------------------------ |
| `employee_identifier`       | AcquiredCo employee identifier |
| `name.first`                | Employee first name            |
| `name.last`                 | Employee last name             |
| `name.full`                 | Full employee name             |
| `contact.email`             | Employee email address         |
| `assignment.department`     | Source department value        |
| `assignment.role`           | Job title or role              |
| `assignment.location`       | Employee location or country   |
| `assignment.hire_timestamp` | Hire timestamp                 |
| `employment.type`           | Employment type                |
| `employment.status`         | Employment status              |
| `manager_employee_id`       | Source manager employee ID     |
| `source_system`             | Source system label            |

### 2.3 Payroll

**Path:** `data/raw/payroll_data.xlsx`
**Format:** Excel `.xlsx`
**System role:** Compensation enrichment source

Expected source columns:

| Column             | Description                                         |
| ------------------ | --------------------------------------------------- |
| `employee_id`      | Source employee ID                                  |
| `source`           | Company origin                                      |
| `base_salary`      | Source salary amount                                |
| `currency`         | Salary currency                                     |
| `pay_frequency`    | Pay frequency such as annual, monthly, or bi-weekly |
| `bonus_target_pct` | Bonus target percentage                             |
| `effective_date`   | Compensation effective date                         |
| `source_system`    | Source system label                                 |

Payroll records enrich HRIS employee identities. Payroll-only records do not create golden employee records; they are treated as ghost employee candidates.

### 2.4 Benefits

**Path:** `data/raw/benefits_enrollment.xml`
**Format:** XML
**System role:** Benefits enrollment enrichment source

Expected source fields:

| Field              | Description              |
| ------------------ | ------------------------ |
| `employee_id`      | Source employee ID       |
| `plan_type`        | Benefits plan type       |
| `coverage_level`   | Coverage level           |
| `enrollment_date`  | Benefits enrollment date |
| `premium_employee` | Employee premium amount  |
| `premium_employer` | Employer premium amount  |
| `source_system`    | Source system label      |

Benefits records enrich HRIS employee identities. Benefits-only records do not create golden employee records; they are treated as ghost employee candidates.

### 2.5 Reference Data

Reference files are stored in `data/reference/`.

| File                     | Description                                                         |
| ------------------------ | ------------------------------------------------------------------- |
| `department_mapping.csv` | Maps source department values to a standardized department taxonomy |

The department mapping is handled through reference data rather than hardcoded logic so that business taxonomy changes can be reviewed and updated without modifying transformation code.

## 3. Pipeline Architecture

The pipeline is orchestrated through:

```bash
src/hr_pipeline/pipeline.py
```

Main modules:

| Module         | Purpose                                                                     |
| -------------- | --------------------------------------------------------------------------- |
| `ingest.py`    | Loads raw CSV, JSON, Excel, and XML files                                   |
| `clean.py`     | Standardizes names, IDs, dates, departments, employment types, and salaries |
| `dedup.py`     | Resolves employee identity records and creates duplicate review outputs     |
| `validate.py`  | Runs data-quality checks and exports validation reports                     |
| `visualize.py` | Generates required EDA charts                                               |
| `pipeline.py`  | Orchestrates the full end-to-end workflow                                   |

Pipeline flow:

```text
Raw source files
    ↓
Ingestion
    ↓
Schema alignment
    ↓
Cleaning and standardization
    ↓
Exact-ID integration
    ↓
Duplicate and fuzzy match review generation
    ↓
Data quality validation
    ↓
Output export
    ↓
Visualization
```

## 4. Key Business Rules

### 4.1 Identity Source of Truth

GlobalTech HRIS and AcquiredCo HRIS are treated as the source of truth for employee identity.

Payroll and benefits records are used only to enrich existing HRIS employee records.

### 4.2 Employee ID Namespacing

Employee IDs are namespaced to prevent collisions between GlobalTech and AcquiredCo.

Examples:

| Source                 | Canonical ID |
| ---------------------- | ------------ |
| GlobalTech `1`         | `GT-000001`  |
| AcquiredCo `ACQ_00001` | `AC-000001`  |

### 4.3 Deduplication Logic

The pipeline uses the following identity-resolution strategy:

1. Build the employee identity spine from HRIS records only.
2. Deduplicate duplicate HRIS employee IDs using deterministic survivor selection.
3. Enrich HRIS records with payroll and benefits data by exact namespaced employee ID.
4. Isolate unmatched payroll or benefits records as ghost employee records.
5. Generate probable match candidates for HR review using:
   - same full name across companies with hire dates within 30 days
   - RapidFuzz name similarity score of at least 88 with hire dates within 30 days

6. Do not auto-merge fuzzy matches.

### 4.4 Salary Normalization

Payroll salaries are normalized to annual USD using fixed exchange rates and pay-frequency multipliers.

The pipeline does not silently correct suspicious compensation values. Instead, salary outliers are flagged by validation and exported for review.

### 4.5 Validation Gate

The validation layer runs 14 data-quality checks. The pipeline gate fails only if more than 2 checks fail.

This allows the pipeline to produce outputs when minor data-quality issues exist, while still making those issues visible through validation reports.

## 5. Output Files

### 5.1 Golden Employee Dataset

**Path:** `data/processed/golden_employee_dataset/`
**Format:** Partitioned Parquet
**Partition column:** `company_origin`

Description:

The golden employee dataset contains one trusted employee record per canonical employee ID. It includes standardized identity, organization, compensation, benefits, provenance, and deduplication fields.

Key fields include:

| Column                    | Description                                              |
| ------------------------- | -------------------------------------------------------- |
| `employee_id`             | Canonical namespaced employee ID                         |
| `source_employee_id`      | Original source employee ID                              |
| `company_origin`          | GlobalTech or AcquiredCo                                 |
| `full_name`               | Standardized full name                                   |
| `email`                   | Standardized lowercase email                             |
| `department_standardized` | Standardized department taxonomy                         |
| `employment_type`         | Standardized employment type                             |
| `manager_id`              | Canonical manager employee ID                            |
| `hire_date`               | Standardized hire date                                   |
| `salary_usd_annual`       | Annualized salary in USD                                 |
| `benefits_enrolled`       | Boolean benefits enrollment flag                         |
| `source_systems`          | Pipe-delimited source systems contributing to the record |
| `dedup_method`            | Deduplication method used                                |

### 5.2 Review and Exception Reports

All review and exception files are written to `data/reports/`.

| File                                   | Format | Description                                                                    |
| -------------------------------------- | ------ | ------------------------------------------------------------------------------ |
| `ghost_employee_records.csv`           | CSV    | Payroll or benefits records without matching HRIS identity                     |
| `duplicate_hris_records.csv`           | CSV    | Duplicate HRIS identity records preserved for audit review                     |
| `duplicate_employee_id_records.csv`    | CSV    | Duplicate employee IDs found in the final golden dataset, expected to be empty |
| `duplicate_email_records.csv`          | CSV    | Cross-company duplicate email candidates                                       |
| `probable_match_review.csv`            | CSV    | Fuzzy or same-name candidate matches for HR review                             |
| `salary_usd_annual_range_failures.csv` | CSV    | Salary records that failed expected annual USD range validation                |
| `data_quality_validation_report.csv`   | CSV    | Validation summary report                                                      |
| `data_quality_validation_report.html`  | HTML   | HTML version of validation summary report                                      |

### 5.3 Probable Match Review File

**Path:** `data/reports/probable_match_review.csv`

This file is designed for HR review and includes the required fields:

| Column                | Description                           |
| --------------------- | ------------------------------------- |
| `record_1_id`         | First employee record ID              |
| `record_2_id`         | Second employee record ID             |
| `similarity_score`    | Name similarity score                 |
| `hire_date_diff_days` | Difference between hire dates in days |
| `recommended_action`  | Recommended review action             |
| `match_type`          | Match logic used                      |
| `left_full_name`      | Name from first record                |
| `right_full_name`     | Name from second record               |
| `left_email`          | Email from first record               |
| `right_email`         | Email from second record              |

The recommended action is `HR_REVIEW`. The pipeline does not automatically merge these records.

### 5.4 Visualizations

Charts are exported to:

```text
data/reports/figures/
```

Required charts:

| File                                         | Description                               |
| -------------------------------------------- | ----------------------------------------- |
| `headcount_by_department.png`                | Headcount by standardized department      |
| `headcount_by_country.png`                   | Headcount by country                      |
| `salary_by_employment_type.png`              | Salary distribution by employment type    |
| `tenure_distribution.png`                    | Employee tenure distribution              |
| `benefits_enrollment_rate_by_department.png` | Benefits enrollment rate by department    |
| `data_quality_summary.png`                   | Passed vs failed validation rows by check |

All charts are exported as 300-DPI PNG files with titles, axis labels, and source annotations.

## 6. How to Run the Pipeline

### 6.1 Create and Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 6.2 Install Dependencies

```bash
pip install -r requirements.txt
```

Expected dependencies include:

```text
pandas
openpyxl
pyarrow
matplotlib
rapidfuzz
```

### 6.3 Run the Pipeline

From the `src` directory:

```bash
python3 -m hr_pipeline.pipeline
```

The pipeline will:

1. Ingest all raw source files.
2. Align source schemas.
3. Clean and standardize fields.
4. Build the golden employee dataset.
5. Generate review files.
6. Run validation checks.
7. Export reports and processed data.
8. Generate visualization PNGs.

## 7. Known Limitations and Assumptions

### 7.1 Fixed Exchange Rates

Currency conversion uses fixed exchange rates for deterministic pipeline output. A production system should use a governed exchange-rate reference table with effective dates.

### 7.2 Fuzzy Matches Are Review-Only

RapidFuzz probable matches are not automatically merged. They are exported for HR confirmation or rejection.

### 7.3 Salary Outliers Are Not Corrected

The pipeline flags suspicious annualized salaries but does not alter them. Salary outliers are exported to `salary_usd_annual_range_failures.csv`.

### 7.4 Payroll and Benefits Are Not Identity Sources

Payroll-only and benefits-only records do not create golden employees. They are isolated as ghost employee candidates.

### 7.5 Department Mapping Depends on Reference Data

Department standardization depends on `data/reference/department_mapping.csv`. New source department values must be added to this reference file.

### 7.6 Empty Review Files Are Valid

Some review files may be empty depending on the input data. For example, `ghost_employee_records.csv` can be empty if all payroll and benefits records match HRIS employee IDs.

### 7.7 Local File-Based Pipeline

This project uses local files to simulate a multi-source integration pipeline. In production, these inputs would likely come from APIs, cloud storage, databases, or managed ingestion services.

## 8. Change Log

### Initial Version

- Implemented ingestion for CSV, JSON, Excel, and XML sources.
- Added simulated API pagination for AcquiredCo JSON ingestion.
- Added schema alignment across all sources.
- Implemented employee ID namespacing.
- Added name, email, date, employment type, department, and salary normalization.
- Added department mapping via reference file.
- Implemented exact-ID integration using HRIS as source of truth.
- Added duplicate HRIS identity detection and review output.
- Added ghost employee detection.
- Added same-name and RapidFuzz probable match review logic.
- Added data-quality validation with 14 checks and pipeline gate.
- Exported validation report as CSV and HTML.
- Exported salary validation failure records.
- Exported golden dataset as Parquet partitioned by company origin.
- Exported review files for ghost records, duplicate records, and probable matches.
- Generated six required EDA visualizations as 300-DPI PNG files.
