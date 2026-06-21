# Golden Employee Dataset Schema

## Overview

The golden employee dataset is the trusted, integrated output of the GlobalTech HR data integration pipeline. It contains one record per canonical employee identity after source ingestion, schema alignment, cleaning, deduplication, enrichment, and validation.

The dataset is exported as partitioned Parquet:

```text
data/processed/golden_employee_dataset/
```

Partition column:

```text
company_origin
```

The golden dataset is built from HRIS identity records and enriched with payroll and benefits data. Payroll and benefits records do not create employee identities on their own.

## Dataset Grain

Each row represents one unique employee identity.

Primary key:

```text
employee_id
```

Expected uniqueness rule:

```text
employee_id must be unique across the golden dataset.
```

## Schema

| Column                        | Data Type | Nullable | Description                                                       | Source / Derivation                                      | Business Rule                                                                               |                     |                 |           |
| ----------------------------- | --------: | -------: | ----------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------- | --------------- | --------- |
| `employee_id`                 |    string |       No | Canonical employee identifier used by the pipeline.               | Derived from source employee ID and company origin.      | Must match `GT-000001` or `AC-000001` format. Must be unique.                               |                     |                 |           |
| `source_employee_id`          |    string |      Yes | Original employee identifier from the source system.              | GlobalTech HRIS, AcquiredCo HRIS, Payroll, Benefits.     | Preserved for traceability back to source records.                                          |                     |                 |           |
| `company_origin`              |    string |       No | Company where the employee originated.                            | Derived from source system or payroll source field.      | Allowed values: `GlobalTech`, `AcquiredCo`. Used as Parquet partition column.               |                     |                 |           |
| `first_name`                  |    string |      Yes | Standardized employee first name.                                 | HRIS sources.                                            | Names are Unicode-normalized and title-cased where applicable.                              |                     |                 |           |
| `last_name`                   |    string |      Yes | Standardized employee last name.                                  | HRIS sources.                                            | Names are Unicode-normalized and title-cased where applicable.                              |                     |                 |           |
| `full_name`                   |    string |       No | Standardized full employee name.                                  | Derived from first and last name, or source full name.   | Must not be null in the golden dataset.                                                     |                     |                 |           |
| `email`                       |    string |       No | Standardized employee email address.                              | HRIS sources.                                            | Lowercased and validated against basic email pattern.                                       |                     |                 |           |
| `department`                  |    string |      Yes | Original source department value.                                 | HRIS sources.                                            | Preserved for lineage and review.                                                           |                     |                 |           |
| `department_standardized`     |    string |       No | Standardized department taxonomy value.                           | Derived using `data/reference/department_mapping.csv`.   | Must not be null after mapping.                                                             |                     |                 |           |
| `job_title`                   |    string |      Yes | Employee job title or role.                                       | HRIS sources.                                            | Preserved from source where available.                                                      |                     |                 |           |
| `manager_id`                  |    string |      Yes | Canonical employee ID of the employee’s manager.                  | HRIS sources, normalized using company origin.           | If present, must refer to an existing `employee_id` in the golden dataset.                  |                     |                 |           |
| `employment_type`             |    string |      Yes | Standardized employment type.                                     | HRIS sources.                                            | Allowed values: `Full-Time`, `Part-Time`, `Contractor`.                                     |                     |                 |           |
| `country`                     |    string |      Yes | Employee country or location.                                     | HRIS sources.                                            | Used for workforce distribution analysis.                                                   |                     |                 |           |
| `jurisdiction`                |    string |      Yes | Jurisdiction or regional classification if available.             | Derived or reserved field.                               | May be null if no jurisdiction mapping is implemented.                                      |                     |                 |           |
| `hire_date`                   |  datetime |       No | Standardized employee hire date.                                  | HRIS sources.                                            | Must be within plausible range and not in the future.                                       |                     |                 |           |
| `salary_original`             |     float |      Yes | Original salary amount after numeric parsing.                     | Payroll source.                                          | May be null when no payroll match exists.                                                   |                     |                 |           |
| `currency`                    |    string |      Yes | Source salary currency.                                           | Payroll source.                                          | Expected values include `USD`, `EUR`, `GBP`.                                                |                     |                 |           |
| `pay_frequency`               |    string |      Yes | Source pay frequency.                                             | Payroll source.                                          | Used to annualize salary. Examples: `Annual`, `Monthly`, `Bi-Weekly`.                       |                     |                 |           |
| `compensation_effective_date` |  datetime |      Yes | Effective date for the payroll compensation record.               | Payroll source.                                          | Latest payroll record is selected when duplicate payroll records exist.                     |                     |                 |           |
| `salary_usd_annual`           |     float |      Yes | Salary normalized to annual USD.                                  | Derived from salary amount, currency, and pay frequency. | Must be between expected business range when present. Outliers are reported, not corrected. |                     |                 |           |
| `benefits_enrolled`           |   boolean |       No | Indicates whether the employee has a benefits enrollment record.  | Benefits source.                                         | Defaults to `False` when no matching benefits record exists.                                |                     |                 |           |
| `benefits_enrollment_date`    |  datetime |      Yes | Date of benefits enrollment.                                      | Benefits source.                                         | May be null if employee is not enrolled or no benefits record exists.                       |                     |                 |           |
| `source_system`               |    string |       No | Primary source system for the identity record.                    | HRIS source.                                             | For golden identity rows, expected values are `globaltech_hris` or `acquiredco_hris`.       |                     |                 |           |
| `source_systems`              |    string |       No | Pipe-delimited list of source systems contributing to the record. | Derived during integration.                              | Examples: `globaltech_hris                                                                  | payroll`, `benefits | globaltech_hris | payroll`. |
| `dedup_method`                |    string |       No | Method used to create or retain the golden record.                | Derived during deduplication.                            | Current value: `exact_employee_id`.                                                         |                     |                 |           |

## Key Derived Fields

### `employee_id`

Employee IDs are namespaced to prevent collisions between GlobalTech and AcquiredCo.

Examples:

| Source Value | Company Origin | Canonical Employee ID |
| ------------ | -------------- | --------------------- |
| `1`          | GlobalTech     | `GT-000001`           |
| `1042`       | GlobalTech     | `GT-001042`           |
| `ACQ_00001`  | AcquiredCo     | `AC-000001`           |
| `ACQ_01042`  | AcquiredCo     | `AC-001042`           |

### `salary_usd_annual`

Annual salary in USD is calculated from:

```text
salary_original × exchange_rate_to_usd × pay_frequency_multiplier
```

Example pay-frequency multipliers:

| Pay Frequency | Multiplier |
| ------------- | ---------: |
| `Annual`      |          1 |
| `Monthly`     |         12 |
| `Bi-Weekly`   |         26 |

Salary outliers are not overwritten. They are exported to:

```text
data/reports/salary_usd_annual_range_failures.csv
```

### `source_systems`

This field records all systems that contributed to the employee record.

Examples:

| Value             | Meaning                                   |                                                |                                                             |
| ----------------- | ----------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| `globaltech_hris` | Identity record only from GlobalTech HRIS |                                                |                                                             |
| `acquiredco_hris  | payroll`                                  | AcquiredCo HRIS identity enriched with payroll |                                                             |
| `benefits         | globaltech_hris                           | payroll`                                       | GlobalTech HRIS identity enriched with payroll and benefits |

### `dedup_method`

Current supported value:

| Value               | Meaning                                                                               |
| ------------------- | ------------------------------------------------------------------------------------- |
| `exact_employee_id` | Employee record was retained or integrated using exact canonical employee ID matching |

Fuzzy matching does not change this field because fuzzy matches are not automatically merged into the golden dataset.

## Validation Rules

The golden dataset is validated using `DataQualityValidator`.

Validation report outputs:

```text
data/reports/data_quality_validation_report.csv
data/reports/data_quality_validation_report.html
```

Current validation checks include:

| Check                              | Description                                                       |
| ---------------------------------- | ----------------------------------------------------------------- |
| `employee_id_not_null`             | Employee ID must not be null.                                     |
| `employee_id_unique`               | Employee ID must be unique across the dataset.                    |
| `employee_id_format`               | Employee ID must match canonical ID format.                       |
| `full_name_not_null`               | Full name must not be null.                                       |
| `email_not_null`                   | Email must not be null.                                           |
| `email_format`                     | Email must match a basic valid email pattern.                     |
| `company_origin_allowed`           | Company origin must be GlobalTech or AcquiredCo.                  |
| `employment_type_allowed`          | Employment type must be an allowed value.                         |
| `department_standardized_not_null` | Standardized department must not be null.                         |
| `hire_date_not_null`               | Hire date must not be null.                                       |
| `hire_date_plausible_range`        | Hire date must be within a plausible range and not in the future. |
| `salary_usd_annual_range`          | Annual salary must be within expected range when present.         |
| `manager_id_referential_integrity` | Manager ID must refer to an existing employee when present.       |
| `benefits_enrolled_boolean`        | Benefits enrollment flag must be boolean.                         |

The quality gate fails if more than two validation checks fail.

## Related Review Files

The golden dataset should be interpreted alongside the review files in `data/reports/`.

| File                                   | Description                                                                     |
| -------------------------------------- | ------------------------------------------------------------------------------- |
| `ghost_employee_records.csv`           | Payroll or benefits records without a matching HRIS identity.                   |
| `duplicate_hris_records.csv`           | Duplicate HRIS identity records preserved for audit review.                     |
| `duplicate_employee_id_records.csv`    | Duplicate employee IDs found in the final golden dataset. Expected to be empty. |
| `duplicate_email_records.csv`          | Cross-company duplicate email candidates.                                       |
| `probable_match_review.csv`            | Same-name or fuzzy-match candidate pairs for HR review.                         |
| `salary_usd_annual_range_failures.csv` | Salary records outside expected annual USD range.                               |

## Notes for Consumers

- The golden dataset contains trusted employee identities, not every raw source row.
- Payroll and benefits are enrichment sources only.
- Probable matches are review candidates only and are not automatically merged.
- Empty review files are valid and indicate no records met that exception condition.
- Salary outliers are intentionally retained in the golden dataset and surfaced through validation outputs.
- The Parquet dataset is partitioned by `company_origin` to support efficient company-level reads.
