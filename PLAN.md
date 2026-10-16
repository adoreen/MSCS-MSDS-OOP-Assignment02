# Implementation Plan — OOP with Python, Assignment 2 (Advent 2026)

## Global requirements (apply to both projects)

- [ ] One GitHub repo link submitted on Moodle.
- [ ] One notebook per mini-project; reusable logic in `src/`, imported into notebooks.
- [ ] `README.md` (setup, how to run, summary of findings, **AI-use declaration**), `requirements.txt`, `tests/`.
- [ ] Seeds fixed with `np.random.default_rng(seed)` wherever randomness appears.
- [ ] Each notebook passes **Restart & Run All** (verified headless with nbconvert).
- [ ] Be ready to explain every line in a viva.

Rubric (each project): Correctness 45% · OOP design 30% · Visualisation 10% · Tests/reproducibility 10% · Extension 5%.

## Repository layout

```
project1_weather.ipynb
project2_uganda_tax.ipynb
src/weather/
    http.py          # fetch_json(): timeout, raise_for_status, retry+backoff, WeatherAPIError
    geocoding.py     # geocode(name) -> list[Location]; choose_location()
    forecast.py      # get_forecast(lat, lon, days); to_dataframe(); WMO code map
    metno.py         # MET Norway client + daily aggregation (Part C)
    plotting.py      # temperature range + precipitation chart
    exceptions.py
src/uganda_tax/
    money.py         # Money value object (Decimal, UGX, rounding, dunders)
    exceptions.py    # TaxError > InvalidIncomeError, NoScheduleForDateError
    context.py       # TaxContext, TaxResult dataclasses
    base.py          # abstract Tax(ABC).calculate(ctx) -> TaxResult
    schedules.py     # Band, ProgressiveSchedule, dated schedule registry
    paye.py  nssf.py  lst.py  vat.py  cit.py
    payroll.py       # PayrollPipeline (composition of Tax objects)
    planner.py       # Extension B: TaxPlanner
tests/
    fixtures/weather/*.json   # saved API responses for offline tests
    test_weather_*.py
    test_money.py test_paye_boundaries.py test_properties.py test_vat.py ...
```

## Mini-Project 1 — Weather forecast via web APIs

**Part A (HTTP basics)**
1. Geocode "Dresden" with only `urllib.request` + `urllib.parse.urlencode` + `json`.
2. Repeat with `requests.get(url, params=..., timeout=...)`.
3. Markdown comparison: code length, error handling, header/encoding control.
4. Report status code, `Content-Type`, and response time (`response.elapsed` / `time.perf_counter`).

**Part B (Retrieval and display)**
1. `geocode(name)`: use `.get("results", [])` because the key is missing when nothing matches → raise/return empty; with several matches ("Springfield"), list them (name, admin1, country, lat/lon) and pick one. The pick must not block Restart & Run All, so it comes from the config cell (e.g. `CHOICE_INDEX = 0`), with `input()` only as an optional interactive mode.
2. `get_forecast(lat, lon, days)`: `daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code`, `timezone=auto`.
3. `to_dataframe()`: columns with units, e.g. `Max temp (°C)`; map WMO weather codes to descriptions.
4. Output: text summary + formatted table + chart (min–max temperature band/lines on one axis, precipitation bars on a twin axis; axis labels with units, title, legend, source credit).

**Part C (Robustness)**
1. `fetch_json(url, params, *, timeout, retries, backoff)`: retry on `ConnectionError`, `Timeout`, 5xx (and 429); exponential backoff `base * 2**attempt`, with a cap; do not retry 4xx; raise `WeatherAPIError` at the end with the cause chained.
2. Demonstrate: an invalid city, latitude=999 (Open-Meteo returns 400), no network (monkeypatch `requests.Session.get` to raise `ConnectionError`, or use an unroutable host), `timeout=0.001`.
3. Second source: MET Norway `compact` endpoint. It **requires** a User-Agent with a contact address, taken from the `CONTACT_EMAIL` env var or config cell, never hardcoded. Aggregate its hourly data to daily min/max and compare it with Open-Meteo in a table or chart.

**Part D (Report, 1,000–1,500 words in Markdown)**: data-flow diagram (ASCII/Mermaid), licences (Open-Meteo CC BY 4.0, free non-commercial tier; MET Norway CC BY 4.0 / NLOD, terms of service, User-Agent rule, caching with `If-Modified-Since`), reliability issues met, privacy of location queries.

**Tests (≥5, offline)**: parse geocode results (normal, empty/missing key, ambiguous), forecast→DataFrame columns/units/dtypes, weather-code mapping (known + unknown), MET Norway daily aggregation, and the retry logic with a mocked session (retries on 503, stops on 404, custom exception).

## Mini-Project 2 — Uganda Tax Engine (OOP required)

**Core design**
- `Money`: frozen dataclass wrapping `Decimal`, currency UGX; rejects `float` input; `ROUND_HALF_UP` to whole shillings (documented); `__add__ __sub__ __mul__ __lt__ __le__ __eq__ __repr__ __bool__`; ordering via `functools.total_ordering`.
- `TaxContext` (gross, allowances, residency, date, invoices, revenue, deductions, …) and `TaxResult` (tax name, amount, breakdown lines, schedule version).
- `Tax(ABC)` with `calculate(self, ctx: TaxContext) -> TaxResult`; subclasses `PAYE`, `NSSF`, `LocalServiceTax`, `VAT`, `CorporateIncomeTax`.
- `ProgressiveSchedule` built from `Band`s (data, not `if` chains) and registered by effective date range; asking for a date outside every range raises `NoScheduleForDateError`. Residents and non-residents get separate schedules on the same engine.
- Exceptions: `TaxError` → `InvalidIncomeError`, `NoScheduleForDateError` (plus `InvalidSupplyError`, etc. if needed). Validate inputs; never fail silently.

**Rules (confirm against current URA publications and cite the version/date)**
- PAYE resident monthly: 0 ≤ 335k; 20% of 335k–410k; 15,000 + 25% of 410k–485k; 33,750 + 30% of 485k–10M; +10% of the excess over 10M.
- PAYE non-resident: own bands (expected 10% / 20% / 30% + 10% surcharge; **verify on ura.go.ug**).
- NSSF: employee 5%, employer 10% of gross.
- LST: configurable annual amount by income band, spread over the instalment months; applied before PAYE as the brief says.
- VAT: 18% standard, 0% zero-rated, exempt (no output VAT, and no input credit for it); net = output − input.
- CIT: (revenue − allowable deductions) × 30%, with a floor at zero chargeable income (losses reported, not taxed).

**Payroll pipeline**: compose the Tax objects → gross + allowances → NSSF → LST → PAYE → net pay. Justify the order in the notebook (what forms the PAYE base: is NSSF deductible for PAYE in Uganda? (No, so PAYE is on gross taxable pay.) LST is deducted before PAYE per the brief).

**Extension**: **B (TaxPlanner)**, comparing salary versus dividend (dividend WHT 15% for residents after CIT on profits), with a thoughtful write-up. It reuses the existing classes, so it is cheaper than A.

**Tests**
- Boundaries: 335,000 / 335,001 / 410,000 / 485,000 / 10,000,000 / 10,000,001 with hand-calculated expected values.
- Hypothesis: tax ≥ 0, monotonic non-decreasing in income, tax ≤ income; Money arithmetic properties.
- Unit tests: Money (float rejected, rounding), VAT mixed invoices, CIT, exceptions raised, schedule lookup by date.

**Report**: (1) float is unsafe: `0.1 + 0.2 != 0.3`, plus a PAYE example where float drifts by a shilling, shown in code; (2) inheritance is justified for `Tax` subclasses and the exception tree; it was avoided for bands and schedules (data plus composition) and in `Money` (composition over subclassing `Decimal`).

## Suggested order of work

1. MP2 core: Money → exceptions → schedules → PAYE + boundary/property tests (most marks, pure logic).
2. MP2 NSSF, LST, payroll pipeline, VAT, CIT, planner, notebook.
3. MP1 http/geocode/forecast modules + saved fixtures + tests.
4. MP1 notebook Parts A–C, then the report (Part D).
5. README (findings, AI declaration), headless run of both notebooks, push to GitHub.

## Commands

```powershell
.venv\Scripts\Activate.ps1
pytest
jupyter lab                       # choose kernel "Python (advent2026)"
jupyter nbconvert --to notebook --execute --inplace project2_uganda_tax.ipynb   # Restart & Run All check
```
