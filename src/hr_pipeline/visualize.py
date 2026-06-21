from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from hr_pipeline.utils.logging import get_logger

logger = get_logger(__name__)

CHART_DPI = 300
EMPLOYEE_COUNT_LABEL = "Employee Count"


def _add_source_note(fig: plt.Figure) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fig.text(
        0.01,
        0.01,
        f"Source: GlobalTech HR integration pipeline | Generated: {timestamp}",
        ha="left",
        fontsize=8,
    )


def _save_chart(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_path, dpi=CHART_DPI, bbox_inches="tight")
    plt.close(fig)

    logger.info("Exported chart to %s", output_path)


def plot_headcount_by_department(golden: pd.DataFrame, output_dir: Path) -> None:
    counts = (
        golden["department_standardized"]
        .fillna("Unknown")
        .value_counts()
        .sort_values(ascending=True)
    )

    fig, ax = plt.subplots(figsize=(10, 7))
    counts.plot(kind="barh", ax=ax)

    ax.set_title("Headcount by Department")
    ax.set_xlabel(EMPLOYEE_COUNT_LABEL)
    ax.set_ylabel("Department")

    _add_source_note(fig)
    _save_chart(fig, output_dir / "headcount_by_department.png")


def plot_headcount_by_country(
    golden: pd.DataFrame,
    output_dir: Path,
    top_n: int = 15,
) -> None:
    counts = (
        golden["country"]
        .fillna("Unknown")
        .value_counts()
        .head(top_n)
        .sort_values(ascending=True)
    )

    fig, ax = plt.subplots(figsize=(10, 7))
    counts.plot(kind="barh", ax=ax)

    ax.set_title(f"Headcount by Country - Top {top_n}")
    ax.set_xlabel(EMPLOYEE_COUNT_LABEL)
    ax.set_ylabel("Country")

    _add_source_note(fig)
    _save_chart(fig, output_dir / "headcount_by_country.png")


def plot_salary_by_employment_type(golden: pd.DataFrame, output_dir: Path) -> None:
    salary_df = golden[
        golden["salary_usd_annual"].notna()
    ].copy()

    fig, ax = plt.subplots(figsize=(9, 6))

    salary_df.boxplot(
        column="salary_usd_annual",
        by="employment_type",
        ax=ax,
        grid=False,
    )

    fig.suptitle("")
    ax.set_title("Annual Salary by Employment Type")
    ax.set_xlabel("Employment Type")
    ax.set_ylabel("Annual Salary USD")

    _add_source_note(fig)
    _save_chart(fig, output_dir / "salary_by_employment_type.png")


def plot_tenure_distribution(golden: pd.DataFrame, output_dir: Path) -> None:
    tenure_df = golden[
        golden["hire_date"].notna()
    ].copy()

    today = pd.Timestamp.today().normalize()
    tenure_df["tenure_years"] = (
        today - pd.to_datetime(tenure_df["hire_date"])
    ).dt.days / 365.25

    fig, ax = plt.subplots(figsize=(9, 6))
    tenure_df["tenure_years"].plot(kind="hist", bins=30, ax=ax)

    ax.set_title("Employee Tenure Distribution")
    ax.set_xlabel("Tenure Years")
    ax.set_ylabel(EMPLOYEE_COUNT_LABEL)

    _add_source_note(fig)
    _save_chart(fig, output_dir / "tenure_distribution.png")


def plot_benefits_enrollment_rate_by_department(
    golden: pd.DataFrame,
    output_dir: Path,
) -> None:
    benefits_df = golden.copy()
    benefits_df["benefits_enrolled"] = benefits_df["benefits_enrolled"].astype(bool)

    enrollment_rate = (
        benefits_df.groupby("department_standardized")["benefits_enrolled"]
        .mean()
        .sort_values(ascending=True)
    )

    fig, ax = plt.subplots(figsize=(10, 7))
    enrollment_rate.plot(kind="barh", ax=ax)

    ax.set_title("Benefits Enrollment Rate by Department")
    ax.set_xlabel("Enrollment Rate")
    ax.set_ylabel("Department")
    ax.set_xlim(0, 1)

    _add_source_note(fig)
    _save_chart(fig, output_dir / "benefits_enrollment_rate_by_department.png")


def plot_data_quality_summary(
    validation_report: pd.DataFrame,
    output_dir: Path,
) -> None:
    report = validation_report.copy()

    fig, ax = plt.subplots(figsize=(12, 7))

    x_positions = range(len(report))
    width = 0.4

    ax.bar(
        [value - width / 2 for value in x_positions],
        report["passed"],
        width=width,
        label="Passed",
    )

    ax.bar(
        [value + width / 2 for value in x_positions],
        report["failed"],
        width=width,
        label="Failed",
    )

    ax.set_title("Data Quality Summary by Check")
    ax.set_xlabel("Validation Check")
    ax.set_ylabel("Row Count")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(report["check"], rotation=45, ha="right")
    ax.legend()

    _add_source_note(fig)
    _save_chart(fig, output_dir / "data_quality_summary.png")


def generate_all_charts(
    golden: pd.DataFrame,
    validation_report: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    Generate all required EDA charts as 300-DPI PNG files.
    """
    plot_headcount_by_department(golden, output_dir)
    plot_headcount_by_country(golden, output_dir)
    plot_salary_by_employment_type(golden, output_dir)
    plot_tenure_distribution(golden, output_dir)
    plot_benefits_enrollment_rate_by_department(golden, output_dir)
    plot_data_quality_summary(validation_report, output_dir)

    logger.info("Generated all EDA charts")