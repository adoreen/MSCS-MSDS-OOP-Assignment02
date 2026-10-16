# OOP with Python: Assignment 2 (Advent 2026)

| Notebook | Mini-project |
|---|---|
| [`project1_weather.ipynb`](project1_weather.ipynb) | Fetching and displaying a weather forecast with Python web APIs (Open-Meteo, MET Norway) |
| [`project2_uganda_tax.ipynb`](project2_uganda_tax.ipynb) | Uganda Tax Engine: PAYE, NSSF, LST, payroll, VAT, CIT, plus extension B (`TaxPlanner`) |

Reusable code lives in `src/weather` and `src/uganda_tax` and is imported by the notebooks. Tests live in `tests/`.

```
src/weather/       http.py (retrying fetch_json) · config.py (contact email, User-Agent) · geocoding.py · forecast.py
                   metno.py · plotting.py · simulate.py (simulated failures) · exceptions.py
src/uganda_tax/    money.py · exceptions.py · context.py · base.py (abstract Tax) · schedules.py · rates.py
                   paye.py · nssf.py · lst.py · vat.py · cit.py · payroll.py · planner.py · plots.py · tables.py
scripts/           capture_fixtures.py (re-captures the saved API samples; needs CONTACT_EMAIL)
tests/             test_weather.py (offline, uses tests/fixtures/weather/*.json)
                   test_money.py · test_paye.py (band edges) · test_properties.py (hypothesis) · test_other_taxes.py
```

## Setup

Requires Python 3.11+ (developed on 3.13).

```bash
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt     # also installs src/ in editable mode
python -m ipykernel install --user --name advent2026 --display-name "Python (advent2026)"
```

The brief requires your university email in the `User-Agent` of every request (MET Norway also insists on it).
Provide it through an environment variable, so it is never stored in the code:

```powershell
$env:CONTACT_EMAIL = "your.name@university.ac.ug"     # PowerShell
export CONTACT_EMAIL="your.name@university.ac.ug"     # bash
```

Without it, the notebook prints a warning, identifies itself by application name only, and replaces the live MET
Norway call with a saved sample, so it still runs end to end. To refresh the saved samples used by the offline tests:
`python scripts/capture_fixtures.py` (one request per file).

## Running

```bash
pytest                                   # 70 tests, fully offline
jupyter lab                              # open a notebook, choose kernel "Python (advent2026)", Restart & Run All
jupyter nbconvert --to notebook --execute --inplace project1_weather.ipynb      # headless check
jupyter nbconvert --to notebook --execute --inplace project2_uganda_tax.ipynb
```

`project1_weather.ipynb` needs internet access. The only manual input is its first configuration cell (location
and contact email). `project2_uganda_tax.ipynb` runs offline. Random draws use `np.random.default_rng(2026)`, and
the hypothesis tests are derandomised (`tests/conftest.py`).

## Summary of findings

### Mini-Project 1: weather forecast
* `requests` replaces about 8 lines of `urllib` plumbing (query encoding, charset decoding, JSON parsing) with one
  call, and gives a clearer exception hierarchy and access to timing information.
* The geocoder omits the `results` key when nothing matches, and returns loosely matching places (for example,
  "Palmyra" for *Springfield*). The code raises `LocationNotFoundError` or asks the user to choose, instead of
  guessing.
* All requests go through one wrapper with a timeout, `raise_for_status()`, exponential-backoff retries for
  transient failures (connection errors, timeouts, 429, 5xx) and a custom `WeatherAPIError`. Client errors (400)
  fail immediately with the server's reason.
* Open-Meteo returned three real 503 errors in a row during sample capture; the retry wrapper recovered on the
  fourth attempt.
* For Dresden, Open-Meteo and MET Norway agreed on daily max/min temperature to within about 1–1.5 °C on average.
  Precipitation and wind differed more. MET's series is hourly only for about 2–3 days and is in UTC, so it has to
  be aggregated carefully.
* The report (Part D) covers the data flow, licences (both CC BY 4.0; Open-Meteo's free tier is non-commercial only;
  MET Norway's terms require an identifying User-Agent and caching) and the privacy risks of sending location
  queries to third parties.

### Mini-Project 2: Uganda tax engine
* The brief's resident PAYE schedule is **identical to URA's FY 2026/27 table** (Income Tax (Amendment) Act 2026,
  in force 1 July 2026). The engine also holds the FY 2025/26 and non-resident schedules, selected by date and
  residency. Unmodelled dates raise `NoScheduleForDateError`.
* The new schedule lowers PAYE for every resident earning over UGX 235,000 a month, by up to UGX 13,750 a month.
* `float` is demonstrably unsafe: three pay components summing to exactly 335,000 add up to `335000.00000000006`
  as floats and fall into the 20% band. `Decimal`-based `Money` gives the exact result.
* Because LST is a step function deducted before PAYE, **net pay falls** when gross pay crosses an LST band (for
  example, 1,000,000 → 1,000,001 lowers August net pay by about UGX 1,749).
* Extension B: paying profit as **salary** always costs less tax than CIT plus dividend withholding tax (40.5%
  flat). Above about UGX 144 million of annual profit, however, dividends leave more *spendable cash*, because
  15% of the salary budget goes into NSSF savings.

## Data sources and licences
* Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0), geocoding based on GeoNames (CC BY 4.0).
* [MET Norway Locationforecast 2.0](https://api.met.no/weatherapi/locationforecast/2.0/documentation) (CC BY 4.0).
* Tax rates (checked 16 Oct 2026): URA PAYE rates page (<https://ura.go.ug/?p=16453>); KCCA *Local Service Tax
  (Assessment & Payment)* FAQ, Feb 2017 (<https://kcca.go.ug/uDocs/Local_Service_Tax_FAQs.pdf>); PwC Worldwide Tax
  Summaries, Uganda withholding taxes (dividend WHT). Effective dates are in
  [`src/uganda_tax/rates.py`](src/uganda_tax/rates.py) and the tax notebook.

## Declaration of AI use

> **TODO (student):** review and edit this declaration so it accurately describes your own use before submitting.

This project was developed with **Claude Code (Anthropic, Claude Opus 5.5)** used as a coding assistant. It was used
to:

* extract the requirements from the assignment PDF and draft an implementation plan (`PLAN.md`);
* look up and cross-check current URA PAYE, LST and withholding-tax rates and the API providers' terms;
* audit the implementation against the brief and fix the deviations it found;
* generate the initial versions of the `src/` modules, the tests, the notebooks and the draft report text.

All code was run, the test suite and both notebooks were executed end to end, and the outputs (tax amounts,
boundary values, charts) were checked against hand calculations. I have read and understood every line and can
explain it in the viva.
