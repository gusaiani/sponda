# Screening Eval Report

## Overall

| Model | Cases | Pass Rate | Filter-Parse Accuracy | Refusal Rate | p50 Latency (s) | p95 Latency (s) | Mean Cost (USD) | Total Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| gpt-4o | 76 | 90.8% | 90.9% | 87.5% | 5.15 | 13.80 | $0.0157 | $1.1924 |

## gpt-4o

### Per-Category

| Name | Passed | Total | Pass Rate |
|---|---|---|---|
| adversarial | 7 | 8 | 87.5% |
| ambiguous | 4 | 5 | 80.0% |
| direction | 9 | 10 | 90.0% |
| geo | 6 | 8 | 75.0% |
| plain | 24 | 24 | 100.0% |
| refine | 6 | 8 | 75.0% |
| sort | 5 | 5 | 100.0% |
| unsupported | 8 | 8 | 100.0% |

### Per-Language

| Name | Passed | Total | Pass Rate |
|---|---|---|---|
| en | 42 | 46 | 91.3% |
| pt | 27 | 30 | 90.0% |

### Worst Failures

**1. `direction-10`** (direction/en)

- Query: Cheap companies
- Expected: `{"kind": "screen", "filters_any_of": [{"pe10": {"max": 10}}, {"pe10": {"max": 8}}], "min_rows": 6}`
- Observed arguments: `null`
- Observed answer: 'Could you please clarify which specific criteria or metrics you would like to use to define "cheap" companies? For example, are you interested in a low P/E ratio, low P/FCF ratio, or something else entirely? Let me know so I can run a screen tailored to your needs.'
- Guardrail: on_topic
- Reason: expected a screen_companies call but none was observed

**2. `geo-03`** (geo/en)

- Query: German industrial companies
- Expected: `{"kind": "screen", "countries": ["DE"], "sectors": ["Industrials"], "expected_symbols_subset": ["EVDEU1", "EVDEU3"], "min_rows": 2}`
- Observed arguments: `{"countries": ["DE"], "sectors": ["Industrial"]}`
- Observed answer: 'Screening: country=DE, sector=Industrial\n\nNo German industrial companies matched the screen criteria. You may want to broaden your search to include additional sectors or countries.'
- Guardrail: on_topic
- Reason: sectors mismatch: observed=['Industrial'], expected=['Industrials']

**3. `geo-08`** (geo/pt)

- Query: Bancos americanos
- Expected: `{"kind": "screen", "countries": ["US"], "sectors": ["Financial Services"], "expected_symbols_subset": ["EVUSA3"], "min_rows": 1}`
- Observed arguments: `{"countries": ["US"], "sectors": ["Finance"]}`
- Observed answer: 'Screening: country=US, sector=Finance\n\nNão foram encontrados bancos americanos que correspondam aos critérios do Sponda no momento. Considere verificar se há outro setor ou critério específico no qual esteja interessado.'
- Guardrail: on_topic
- Reason: sectors mismatch: observed=['Finance'], expected=['Financial Services']

**4. `refine-03`** (refine/en)

- Query: Drop the Brazilian ones
- Expected: `{"kind": "screen", "filters": {"pe10": {"max": 8}}, "countries": ["US", "DE"], "expected_symbols_subset": ["EVUSA1", "EVUSA5", "EVDEU1", "EVDEU3"], "min_rows": 4}`
- Observed arguments: `{"filters": {"pe10": {"max": 8}}, "countries": [], "sectors": [], "sort": "pe10"}`
- Observed answer: 'Screening: pe10 < 8, excluding Brazilian companies. \n\nThe non-Brazilian companies with PE10 under 8 are:\n\n1. **Micro Value** (Industrials) - PE10: 3.2\n2. **Cheap Tech** (Technology) - PE10: 6.0\n3. **Auto Eval** (Industrials) - PE10: 5.5\n4. **Werk Eval** (Industrials) - PE10: 7.2\n\nThese companies are spread across different sectors, primarily in industries and technology. If you need more details about any specific company, feel free to ask!'
- Guardrail: on_topic
- Reason: countries mismatch: observed=[], expected=['DE', 'US']

**5. `refine-06`** (refine/pt)

- Query: Tire as brasileiras
- Expected: `{"kind": "screen", "filters": {"pe10": {"max": 8}}, "countries": ["US", "DE"], "expected_symbols_subset": ["EVUSA1", "EVUSA5", "EVDEU1", "EVDEU3"], "min_rows": 4}`
- Observed arguments: `{"filters": {"pe10": {"max": 8}}, "countries": [], "sort": "pe10"}`
- Observed answer: 'Screening: pe10 < 8, excluindo empresas brasileiras.\n\nAs empresas que não são brasileiras e têm um P/E10 abaixo de 8 são:\n\n1. **Micro Value (EVUSA5)** - Setor: Industrials, P/E10: 3.2\n2. **Embpar (EPAR3)** - Setor: Producer Manufacturing, P/E10: 4.4\n3. **Auto Eval (EVDEU3)** - Setor: Industrials, P/E10: 5.5\n4. **Cheap Tech (EVUSA1)** - Setor: Technology, P/E10: 6.0\n5. **Werk Eval (EVDEU1)** - Setor: Industrials, P/E10: 7.2\n\nEstas são as empresas que não são do Brasil e têm um P/E10 abaixo de 8. Se precisar de mais informações, estou à disposição!'
- Guardrail: on_topic
- Reason: countries mismatch: observed=[], expected=['DE', 'US']
