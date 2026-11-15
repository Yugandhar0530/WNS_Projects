# Invoice Data Extraction

Streamlit application that extracts structured invoice fields from PDF or image uploads using Tesseract OCR, regular-expression hints, and a local Ollama model via LangChain.

## Features

- **PDF and images** — PNG, JPG, JPEG, and multi-page PDF input
- **OCR** — Tesseract with selectable page-segmentation modes
- **Rule-based hints** — pattern matching for invoice number, date, totals, currency, and vendor name
- **LLM structuring** — `llama3.2`, `llama3`, or `mistral` with JSON output and empty-field stripping
- **Review aids** — OCR text expander, hints expander, and JSON download

## Project Background

Skense delivery training includes computer vision, NLP, and GenAI module development. This project combines document OCR with LangChain prompt templates so trainees can see an end-to-end pipeline from scanned invoices to JSON suitable for downstream APIs or spreadsheets. Rule-based parsing narrows the search space before the model formats the final payload.

## Prerequisites

- Python 3.10 or later
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed on the system PATH, or `TESSERACT_PATH` set to `tesseract.exe` (Windows example: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- [Ollama](https://ollama.com) running locally with at least one model:

```powershell
ollama pull llama3.2
```

Optional models:

```powershell
ollama pull llama3
ollama pull mistral
```

## How to Run

From the repository root:

```powershell
cd WNS_Projects\Invoice_Data_Extraction
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:TESSERACT_PATH = "C:\Program Files\Tesseract-OCR\tesseract.exe"
streamlit run app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).

## User Interface

![Main upload screen with sidebar settings](screenshots/main_ui.png)

The sidebar selects the Ollama model and OCR PSM mode. After upload, the first page preview appears on the left; use **Extract fields** on the right.

## Sample Output

![Structured JSON after successful extraction](screenshots/extraction_result.png)

A successful run shows normalized JSON, a **Download JSON** button, and expanders for raw OCR text and rule-based hints.

![OCR and hints expanders](screenshots/ocr_and_hints.png)

## Extracted JSON Shape

| Field | Description |
| --- | --- |
| `invoice_number` | Identifier on the document |
| `date` | Invoice date (prefer `YYYY-MM-DD`) |
| `vendor_name` | Supplier or issuer |
| `vendor_address` | Issuer address when present |
| `currency` | ISO code or symbol-derived code |
| `total_amount` | Grand total or amount due |
| `subtotal` | Pre-tax subtotal when listed |
| `tax_amount` | Tax line when listed |
| `items` | List of `{description, quantity, unit_price, total_price}` |

## Architecture

| Module | Role |
| --- | --- |
| `ocr_engine.py` | PDF rendering (PyMuPDF), per-page OCR, combined text |
| `rule_hints.py` | Regex and line heuristics for key fields |
| `llm_extractor.py` | LangChain + Ollama JSON extraction |
| `app.py` | Streamlit UI and orchestration |

## Test Cases

### Automated (rule hints)

From `WNS_Projects\Invoice_Data_Extraction` with the virtual environment active:

```powershell
pip install pytest==8.4.1
python -m pytest tests\test_rule_hints.py -v
```

| ID | Case | Steps | Expected |
| --- | --- | --- | --- |
| R1 | Invoice number and total | Run pytest `test_invoice_number_and_total` | Hints include `INV-2024-991`, `1250.50`, vendor line |
| R2 | ISO date and currency | Run pytest `test_iso_date_and_currency` | `date` = `2024-11-01`, `currency` = `USD` |
| R3 | Empty OCR | Run pytest `test_empty_text` | Empty dict `{}` |

### Manual (UI and integrations)

| ID | Feature | Steps | Expected |
| --- | --- | --- | --- |
| M1 | Image upload | Upload a clear PNG/JPG invoice; click **Extract fields** | Preview renders; JSON shows at least one of invoice number, date, or total |
| M2 | PDF upload | Upload a one-page PDF invoice | Same as M1; multi-page PDFs concatenate OCR across pages |
| M3 | PSM modes | Repeat M1 with PSM 6, 3, and 11 | OCR text quality may change; extraction still completes when text is readable |
| M4 | Model switch | Run M1 with each sidebar model (`llama3.2`, `llama3`, `mistral`) | JSON returned; failures show Ollama error message |
| M5 | Download JSON | After M1, click **Download JSON** | File `invoice_fields.json` opens in an editor with the same content as on screen |
| M6 | OCR expander | After M1, open **OCR text** | Raw Tesseract output visible for manual verification |
| M7 | Hints expander | After M1 on a typical invoice | **Rule-based hints** shows matched patterns when regex finds them |
| M8 | No OCR text | Upload a blank white image | Warning: OCR returned no text |
| M9 | Ollama stopped | Stop Ollama service; run M1 | Error: LLM extraction failed |
| M10 | Missing Tesseract | Unset PATH and `TESSERACT_PATH`; run M1 | Empty or failed OCR; warning or error as appropriate |

## Notes

- Best results use high-contrast scans and English text.
- First LLM call after model load may take longer depending on hardware.
- Rule hints are advisory; the model must agree with visible OCR text before values appear in JSON.