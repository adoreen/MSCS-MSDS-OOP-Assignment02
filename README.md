# OOP with Python: Assignment 2 (Advent 2026)

**Course:** MSCS & MSDS, OOP with Python
**Student:** Agaba Allan
**Submission:** two mini-projects, each with a Jupyter notebook, reusable code in `src/`, and tests in `tests/`

| # | Mini-project | Notebook |
|---|---|---|
| 1 | Fetching and displaying a weather forecast with Python web APIs | [`project1_weather.ipynb`](project1_weather.ipynb) |
| 2 | Uganda Tax Engine (OOP), with extension **B: `TaxPlanner`** | [`project2_uganda_tax.ipynb`](project2_uganda_tax.ipynb) |

Both notebooks run top to bottom with **Restart & Run All** and are committed with their outputs.

---

## Contents

1. [Repository structure](#repository-structure)
2. [Setup](#setup)
3. [How to run](#how-to-run)
4. [Where each requirement is met](#where-each-requirement-is-met)
5. [Summary of findings](#summary-of-findings)
6. [Data sources and licences](#data-sources-and-licences)
7. [Declaration of AI use](#declaration-of-ai-use)

---

## Repository structure

```
project1_weather.ipynb        Mini-Project 1 notebook (Parts A–D, including the 1,000–1,500-word report)
project2_uganda_tax.ipynb     Mini-Project 2 notebook (tax engine, payroll, VAT, CIT, extension B, discussion)
src/
  weather/                    Mini-Project 1 package
    http.py                   fetch_json(): timeout, raise_for_status, retries with exponential backoff, WeatherAPIError
    config.py                 contact email (from CONTACT_EMAIL) and the User-Agent sent with every request
    geocoding.py              geocode(), choose_location(), Location
    forecast.py               get_forecast(), forecast_to_dataframe(), WMO weather codes, summarise()
    metno.py                  MET Norway client and hourly-to-daily aggregation
    plotting.py               forecast and comparison charts
    simulate.py               simulated failures (flaky server, no network) for the robustness demos
    exceptions.py             WeatherError hierarchy
  uganda_tax/                 Mini-Project 2 package
    base.py                   abstract Tax with calculate(self, ctx: TaxContext) -> TaxResult
    money.py                  Money value object (Decimal, UGX, explicit rounding, operator overloading)
    exceptions.py             TaxError, InvalidIncomeError, NoScheduleForDateError, ...
    context.py                TaxContext, TaxResult, Invoice, Deduction, Residency
    schedules.py, rates.py    dated rate schedules (data, not if-chains) with cited sources
    paye.py, nssf.py, lst.py, vat.py, cit.py      one class per tax
    payroll.py                PayrollPipeline and Payslip
    planner.py                extension B: TaxPlanner, SalaryScenario, DividendScenario
    plots.py, tables.py       charts and tables for the notebook
tests/                        70 pytest tests, all offline
  fixtures/weather/*.json     saved API responses used by the offline tests
scripts/capture_fixtures.py   re-captures the saved API responses
requirements.txt              dependencies (also installs src/ in editable mode)
```

## Setup

Requires **Python 3.11 or later** (developed on 3.13).

```bash
git clone <this repository>
cd <repository folder>
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name advent2026 --display-name "Python (advent2026)"
```

**Contact email (Mini-Project 1).** The brief requires your university email in the `User-Agent` of every request,
and it must not be hardcoded. Set it as an environment variable before starting Jupyter:

```bash
$env:CONTACT_EMAIL = "your.name@university.ac.ug"     # Windows PowerShell
export CONTACT_EMAIL="your.name@university.ac.ug"     # macOS/Linux
```

If it is not set, the notebook still runs. It prints a warning, identifies itself by application name only, and uses
a saved MET Norway sample instead of a live call.

## How to run

```bash
pytest                       # run the 70 offline tests
jupyter lab                  # open a notebook, choose kernel "Python (advent2026)", then Kernel → Restart & Run All
```

* `project1_weather.ipynb` needs an internet connection. The only manual input is the **configuration cell** at
  the top (location and contact email).
* `project2_uganda_tax.ipynb` runs offline.
* **Reproducibility:** random draws use `np.random.default_rng(2026)`. Hypothesis tests are derandomised in
  `tests/conftest.py`. The weather tests use saved JSON, so live forecast changes never break them.

A headless check that matches *Restart & Run All*:

```bash
jupyter nbconvert --to notebook --execute --inplace project1_weather.ipynb
jupyter nbconvert --to notebook --execute --inplace project2_uganda_tax.ipynb
```

## Where each requirement is met

### General instructions

| Requirement | Where |
|---|---|
| One notebook per mini-project, reusable logic in `src/` | The two notebooks, `src/weather/`, `src/uganda_tax/` |
| README, requirements file, `tests/` folder | This file, `requirements.txt`, `tests/` |
| Seeds fixed with `np.random.default_rng(seed)` | Both notebooks (seed 2026) |
| Restart & Run All without errors | Both notebooks are committed fully executed |
| AI use declared | [Declaration of AI use](#declaration-of-ai-use) |

### Mini-Project 1: weather forecast

| Requirement | Where |
|---|---|
| A1: geocode with `urllib` and `urlencode` only | Notebook, Part A1 |
| A2–A4: `requests` with `params=` and a timeout; comparison; status code, Content-Type and response time | Notebook, Parts A2–A4 |
| B1: `geocode(name)` handles zero results (missing `results` key) and ambiguous names | `src/weather/geocoding.py`; Part B1 ("Springfield") |
| B2: `get_forecast(lat, lon, days)` with daily max/min temperature, precipitation, max wind and local time zone | `src/weather/forecast.py`; Part B2 |
| B3: DataFrame with units; weather codes decoded | `forecast_to_dataframe()`; Part B3 |
| B4: text summary, formatted table, temperature and precipitation chart | Part B4 |
| C1: wrapper with timeout, `raise_for_status()`, exponential backoff with a cap, custom exception | `src/weather/http.py` (`fetch_json`, `RetryPolicy`, `WeatherAPIError`) |
| C2: invalid city, invalid latitude, no network (simulated), tiny timeout | Part C2 |
| Second source (MET Norway) | `src/weather/metno.py`; Part C3 |
| D: 1,000–1,500-word report (data flow diagram, licensing, reliability, privacy) | Part D (about 1,200 words) |
| No hardcoded contact details; email in User-Agent | `src/weather/config.py`, `CONTACT_EMAIL` variable |
| Libraries beyond the allowed list are justified | Table at the top of the notebook |
| At least 5 offline checks on parsing functions, with saved JSON | `tests/test_weather.py` (15 tests), `tests/fixtures/weather/` |

### Mini-Project 2: Uganda Tax Engine

| Requirement | Where |
|---|---|
| Rates confirmed and cited | `src/uganda_tax/rates.py`; notebook "Regulatory baseline" table |
| PAYE: resident and non-resident, progressive bands, 10% surcharge above 10,000,000 | `paye.py`, `rates.py`; notebook §2 |
| Payroll: NSSF, configurable LST, PAYE, net pay; order documented and justified | `payroll.py`; notebook §3 |
| VAT: standard-rated, zero-rated, exempt; output, input and net VAT | `vat.py`; notebook §4 |
| Corporate income tax | `cit.py`; notebook §5 |
| Abstract `Tax` with `calculate(self, ctx: TaxContext) -> TaxResult` | `base.py` |
| `Money` with `Decimal` only, explicit rounding, `__add__`, `__mul__`, `__lt__`, `__repr__` | `money.py`; notebook §1 |
| `TaxError`, `InvalidIncomeError`, `NoScheduleForDateError`; never fail silently | `exceptions.py` |
| Boundary tests: 335,000; 335,001; 410,000; 485,000; 10,000,000; 10,000,001 | `tests/test_paye.py` |
| Hypothesis: non-negative, monotonic in income, never exceeding income | `tests/test_properties.py` |
| Extension B: `TaxPlanner` comparing salary and dividend | `planner.py`; notebook §6 |
| Discussion: why `float` is unsafe (with a failing example); where inheritance is used and avoided | Notebook §1 and §7 |

## Summary of findings

### Mini-Project 1: weather forecast

* **urllib vs requests.** `requests` replaces the manual query encoding, charset decoding and JSON parsing of
  `urllib` with one call. It also has a clearer exception hierarchy and built-in response timing.
* **Missing data and ambiguity.** For an unknown name the geocoder omits the `results` key rather than returning
  an empty list. For "Springfield" it returns ten places, including towns that only match an alternative name. The
  code raises `LocationNotFoundError`, or lists the candidates and asks for a choice, instead of guessing.
* **Reliability.** Every request goes through one wrapper. Transient failures (connection errors, timeouts, 429,
  5xx) are retried with exponential backoff, and bad input (400) fails immediately with the server's reason. This
  was tested for real: Open-Meteo returned three 503 errors in a row while the samples were captured, and the
  wrapper recovered on the fourth attempt.
* **Two sources.** For Dresden, Open-Meteo and MET Norway agree on daily maximum and minimum temperature to within
  about 1–1.5 °C on average. Precipitation and wind differ more. MET's series is in UTC and hourly only for the
  first 2–3 days, so it must be converted and aggregated with care.
* **Licensing and privacy** (Part D). Both sources are CC BY 4.0. Open-Meteo's free tier is for non-commercial use
  only, and MET Norway requires an identifying User-Agent and caching. Location queries reveal where users are, so
  a real product should round coordinates, proxy and cache requests, and send no user identifiers.

### Mini-Project 2: Uganda Tax Engine

* **Rates.** The brief's resident PAYE schedule is identical to URA's FY 2026/27 table (Income Tax (Amendment) Act
  2026, in force 1 July 2026). The engine also holds the FY 2025/26 resident schedule and the non-resident
  schedule, chosen by date and residency. Dates outside these periods raise `NoScheduleForDateError`.
* **Effect of the 2026/27 change.** Every resident earning over UGX 235,000 a month pays less PAYE than in
  FY 2025/26, by up to UGX 13,750 a month.
* **Why not float.** Three pay components that add up to exactly 335,000 give `335000.00000000006` as floats, which
  puts the employee in the 20% band. The `Decimal`-based `Money` class gives the exact answer.
* **An LST "cliff".** LST is a fixed amount per income band and is deducted before PAYE. So net pay can fall when
  gross pay rises: moving from 1,000,000 to 1,000,001 a month lowers August take-home pay by about UGX 1,749.
* **Extension B (salary vs dividend).** Paying profit out as salary always costs less tax than corporate tax plus
  dividend withholding tax (a flat 40.5%). But above about UGX 144 million of annual profit, dividends leave more
  *spendable cash*, because 15% of a salary budget goes into compulsory NSSF savings.

## Data sources and licences

* Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0). Geocoding is based on GeoNames (CC BY 4.0).
* [MET Norway Locationforecast 2.0](https://api.met.no/weatherapi/locationforecast/2.0/documentation) (CC BY 4.0).
* Tax rates, checked 16 October 2026:
  * PAYE: URA PAYE rates page, <https://ura.go.ug/?p=16453>
  * Local Service Tax: KCCA, *Local Service Tax (Assessment & Payment)* FAQ, February 2017,
    <https://kcca.go.ug/uDocs/Local_Service_Tax_FAQs.pdf>
  * Dividend withholding tax: PwC Worldwide Tax Summaries, Uganda, *Withholding taxes*,
    <https://taxsummaries.pwc.com/uganda/corporate/withholding-taxes>
  * Effective dates for every schedule are in [`src/uganda_tax/rates.py`](src/uganda_tax/rates.py).

## Declaration of AI use

I used **Claude Code** (Anthropic's AI coding assistant, model Claude Opus 5.5) throughout this assignment. In
particular, it was used to:

* read the assignment brief and draft an implementation plan (`PLAN.md`);
* look up and cross-check the current URA PAYE, LST and withholding-tax rates, and the Open-Meteo and MET Norway
  terms of service;
* generate the code in `src/`, the tests, the two notebooks and the first draft of the Part D report;
* audit the work against the brief and correct the deviations it found (for example, adding the contact email to
  every User-Agent and removing duplicated code).

My own role was to direct the work, approve the plan (including the choice of extension B), supply the contact
email, ask for the implementation to be checked against the brief, and review the results.
All tests and both notebooks were run end to end before submission. I take responsibility for the submitted code
and am prepared to explain any line of it in a viva.
