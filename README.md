# WNS Projects

Collection of applications for computer vision, NLP, REST APIs, and GenAI development. Each folder is a self-contained application with its own `README.md`, pinned `requirements.txt`, run instructions, screenshots, and test guidance.


**GitHub:** [https://github.com/Yugandhar0530/WNS_Projects](https://github.com/Yugandhar0530/WNS_Projects)

## Projects

### 1. 🚗 [Intelligent Traffic Monitoring System](Intelligent_Traffic_Monitoring_System/)

Offline or webcam video processing with YOLOv8. Detects people and vehicle classes, draws annotated output, and summarizes per-class counts.

| | |
| --- | --- |
| **Use case** | Traffic flow review, vehicle and pedestrian counting on recorded CCTV or dashcam footage |
| **Stack** | YOLOv8, OpenCV, Python |
| **Run** | See project README (`python app.py` with CLI options) |

### 2. 📹 [Real-Time Object Detection](Real_Time_Object_Detection/)

Flask app streaming live webcam frames with YOLOv8 detections to the browser (MJPEG).

| | |
| --- | --- |
| **Use case** | Live workspace or entryway monitoring, quick object-label demos in the browser |
| **Stack** | YOLOv8, Flask, OpenCV |
| **Run** | `python app.py` |

### 3. 🧾 [Invoice Data Extraction](Invoice_Data_Extraction/)

Streamlit pipeline: PDF/image upload, Tesseract OCR, regex hints, LangChain + Ollama JSON extraction, download and review expanders.

| | |
| --- | --- |
| **Use case** | Accounts payable automation, turning scanned invoices into structured JSON for ERP or spreadsheets |
| **Stack** | Tesseract, PyMuPDF, LangChain, Ollama, Streamlit |
| **Run** | `streamlit run app.py` |

### 4. 🌍 [Invoice Language Translation](Invoice_Language_Translation/)

Extracts invoice text from PDFs or images and translates across languages (offline translation stack per project README).

| | |
| --- | --- |
| **Use case** | Cross-border vendors — read foreign-language invoices without sending documents to a cloud translator |
| **Stack** | OCR, Argos Translate, Streamlit |
| **Run** | `streamlit run app.py` |

### 5. 📦 [Invoice Bounding Box Drawing](Invoice_Bounding_Box_Drawing/)

OCR plus LLM-assisted field discovery; draws bounding boxes on invoice images for verification and demos.

| | |
| --- | --- |
| **Use case** | Audit and QA — visually confirm which regions were read for each invoice field |
| **Stack** | Tesseract, LangChain, Ollama, OpenCV, Streamlit |
| **Run** | `streamlit run app.py` |

### 6. 🏷️ [Invoice Categorization and Tagging](Invoice_Categorization_and_Tagging/)

Classifies invoices into departments, expense categories, and tags from OCR text via local LLM.

| | |
| --- | --- |
| **Use case** | Expense routing, cost-center assignment, and searchable tags for finance workflows |
| **Stack** | Tesseract, LangChain, Ollama, Streamlit |
| **Run** | `streamlit run app.py` |

### 7. ✍️ [Text Generator](Text_Generator/)

GenAI text studio: assistant chat (streaming), short stories, and topic jokes using Ollama and LangChain.

| | |
| --- | --- |
| **Use case** | Local GenAI demos — draft copy, playful content, or a sandbox chat without external APIs |
| **Stack** | LangChain, Ollama, Streamlit |
| **Run** | `streamlit run app.py` |

### 8. 💭 [Sentiment Analysis API](Sentiment_Analysis_API/)

REST API for positive / negative / neutral scoring with confidence; Swagger at `/docs`.

| | |
| --- | --- |
| **Use case** | Customer feedback triage, review scoring, and batch sentiment before reporting pipelines |
| **Stack** | FastAPI, TextBlob, Uvicorn |
| **Run** | `uvicorn app:app --reload` |

### 9. 🔒 [Python Website Blocker](Python_Website_Blocker/)

Streamlit tool to block domains via the hosts file, with pattern rules and optional page scraping (admin rights on Windows).

| | |
| --- | --- |
| **Use case** | Productivity and policy control — block distraction sites or bulk domains on a single Windows PC |
| **Stack** | Streamlit, hosts-file edits, requests, BeautifulSoup |
| **Run** | `streamlit run app.py` (elevated when blocking) |

## Technology map

| Area | Libraries / tools used across projects |
| --- | --- |
| Computer vision | YOLOv8, OpenCV |
| OCR / documents | Tesseract, PyMuPDF, Pillow |
| GenAI / NLP | Ollama, LangChain |
| Translation | Argos Translate (invoice translation project) |
| APIs | FastAPI, Flask |
| UI | Streamlit |
| Sentiment | TextBlob |

## Quick start

Each project folder contains:

- `README.md` — background, prerequisites, how to run, screenshots, tests  
- `requirements.txt` — pinned dependency versions  
- Entry point — `app.py`, `main.py`, or as documented per project  

Typical setup from the repository root:

```powershell
cd WNS_Projects\<ProjectFolder>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then follow that project’s README for the exact start command (`streamlit run app.py`, `python app.py`, or `uvicorn app:app --reload`).

### Shared prerequisites (where applicable)

- Python 3.10+
- **Ollama** with models such as `llama3.2`, `llama3`, or `mistral` for LLM-based apps
- **Tesseract OCR** on PATH or `TESSERACT_PATH` set for invoice and OCR projects
- Webcam for live detection demos; sufficient RAM for YOLO and LLM inference

## Project matrix

| Project | Domain | Primary input | Primary output | Model / core |
| --- | --- | --- | --- | --- |
| Intelligent Traffic Monitoring | CV | Video / webcam | Annotated video + counts | YOLOv8 |
| Real-Time Object Detection | CV | Webcam | MJPEG stream | YOLOv8 |
| Invoice Data Extraction | NLP + CV | PDF / image | JSON fields | Tesseract + Ollama |
| Invoice Language Translation | NLP + CV | PDF / image | Translated text | OCR + Argos |
| Invoice Bounding Box Drawing | CV + NLP | PDF / image | Boxed image + JSON | OCR + Ollama |
| Invoice Categorization and Tagging | NLP + CV | PDF / image | Tags / categories JSON | OCR + Ollama |
| Text Generator | GenAI | User prompts | Chat / story / jokes | Ollama |
| Sentiment Analysis API | REST / NLP | Text JSON | Label + confidence | TextBlob |
| Python Website Blocker | Systems | Domain lists | Hosts file rules | Rules + scraping |

## Repository layout

```
WNS_Projects/
├── README.md                          ← this file
├── Intelligent_Traffic_Monitoring_System/
├── Real_Time_Object_Detection/
├── Invoice_Data_Extraction/
├── Invoice_Language_Translation/
├── Invoice_Bounding_Box_Drawing/
├── Invoice_Categorization_and_Tagging/
├── Text_Generator/
├── Sentiment_Analysis_API/
└── Python_Website_Blocker/
```

## Learning outcomes

These projects demonstrate:

- Object detection and video pipelines (YOLOv8)
- OCR and structured document extraction
- LangChain prompts with local LLMs and hallucination controls
- Streamlit and Flask UIs plus a FastAPI REST service
- Hosts-file automation and lightweight web scraping
- README-driven delivery with screenshots and test evidence

## Notes

- Prefer the **project-level README** for screenshots, sample output, and manual test checklists.
- Many apps run entirely on your machine; no cloud API keys are required for the Ollama-based flows.
- Model weights (e.g. `yolov8n.pt`) and Ollama models download on first use where noted in each README.