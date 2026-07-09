# Smart Warehouse Storage Allocation System

A production-ready, full-stack web application that helps warehouse operators
decide **where to store incoming products**. Upload a plain-text product
dataset, configure your warehouse racks, run one of six allocation
algorithms, and review interactive charts, statistics, and AI-generated
recommendations — then export everything as CSV or a formatted PDF report.

![status](https://img.shields.io/badge/status-production--ready-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![flask](https://img.shields.io/badge/flask-3.x-black)

---

## Table of Contents

1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Folder Structure](#folder-structure)
4. [Installation](#installation)
5. [Running the App](#running-the-app)
6. [Dataset Format](#dataset-format)
7. [Allocation Algorithms](#allocation-algorithms)
8. [REST API](#rest-api)
9. [Screenshots](#screenshots)
10. [Troubleshooting](#troubleshooting)

---

## Features

- **Drag-and-drop dataset upload** with row-by-row validation and a detailed error report (duplicate IDs, negative dimensions, missing fields, invalid enums, etc.)
- **Configurable warehouse racks** — edit dimensions, max weight, and storage type directly from the UI
- **Six allocation strategies**: First Fit, Best Fit, Worst Fit, Priority Based, Space Optimized, Weight Balanced
- **Optimization statistics**: total/occupied/unused volume, space utilization %, average rack utilization, weight utilization, and a priority allocation score
- **Interactive dashboard** with pie charts, bar charts, and a warehouse occupancy heatmap (Chart.js)
- **Algorithm comparison view** — run all six strategies against the same dataset side-by-side
- **History** of every upload and allocation run
- **AI Recommendation module** — rule-based analysis of your dataset that recommends the best-fit strategy, an expected utilization estimate, likely bottlenecks, and a future storage growth prediction
- **CSV & PDF export** of any allocation run
- **REST API** (`/api/upload`, `/api/analyze`, `/api/allocate`, `/api/history`, `/api/export`)
- Responsive Bootstrap 5 UI with **dark mode**, sortable/searchable/paginated tables, loading overlays, and upload progress bar

---

## Tech Stack

| Layer            | Technology                          |
|-------------------|--------------------------------------|
| Backend           | Python, Flask                       |
| Database          | SQLite via SQLAlchemy ORM (Flask-SQLAlchemy) |
| Data processing   | Pandas, NumPy                       |
| Visualization     | Chart.js                            |
| PDF generation    | ReportLab                           |
| Frontend          | HTML5, CSS3, Bootstrap 5, vanilla JavaScript, Bootstrap Icons |

---

## Folder Structure

```
warehouse_allocator/
│
├── app.py                 # Flask app factory, page routes, REST API, CSV/PDF export
├── config.py               # Central configuration & enumerations
├── models.py                # SQLAlchemy models (Dataset, Product, Rack, AllocationRun, AllocationResult)
├── parser.py                 # Dataset (.txt) parsing & validation
├── allocation.py              # Six allocation algorithms + statistics engine
├── optimizer.py                # AI recommendation / bottleneck / prediction module
├── requirements.txt
├── database.db               # SQLite database (created automatically on first run)
│
├── templates/
│   ├── base.html              # Shared layout: sidebar, dark mode, loading overlay
│   ├── index.html              # Home / about page
│   ├── upload.html              # Upload + warehouse configuration
│   ├── dashboard.html             # Dataset preview, AI recommendation, run allocation
│   ├── result.html                 # Allocation result detail, charts, heatmap, exports
│   ├── compare.html                  # Side-by-side algorithm comparison
│   └── history.html                   # Upload & run history
│
├── static/
│   ├── css/style.css                    # App theme (warehouse-ops visual language)
│   ├── js/script.js                       # Dark mode, sidebar, sortable/searchable tables
│   └── images/
│
└── uploads/                                # Uploaded dataset files (+ sample_dataset.txt)
```

---

## Installation

**Requirements:** Python 3.10+ and `pip`.

```bash
# 1. Navigate into the project folder
cd warehouse_allocator

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Running the App

```bash
python app.py
```

The app will start on **http://127.0.0.1:5000**. On first launch it automatically:

- Creates `database.db` (SQLite) and all required tables
- Seeds four default racks (Rack A–D) with sample dimensions and types

Open the URL in your browser, then go to **Upload Dataset** and try the
included `uploads/sample_dataset.txt` file to see the system in action.

---

## Dataset Format

Each row is a comma-separated line with **11 fields**:

```
Product ID, Product Name, Length, Width, Height, Weight,
Priority, Storage Type, Fragile(Yes/No), Temperature Requirement, Quantity
```

Example:

```
P101,Chair,40,35,80,10,High,Normal,No,None,12
P102,Glass,30,30,20,2,High,Fragile,Yes,None,15
P103,Frozen Meat,50,40,25,18,Medium,Cold,No,Cold,8
```

**Validation rules:**

| Field                    | Rule                                             |
|--------------------------|---------------------------------------------------|
| Product ID               | Required, must be unique in the file              |
| Product Name             | Required                                          |
| Length / Width / Height  | Positive numbers (cm)                             |
| Weight                   | Positive number (kg)                              |
| Priority                 | `High`, `Medium`, or `Low`                        |
| Storage Type             | `Normal`, `Fragile`, `Cold`, or `Hazardous`        |
| Fragile                  | `Yes` or `No`                                     |
| Temperature Requirement  | `None`, `Cold`, or `Frozen`                       |
| Quantity                 | Positive integer                                  |

Invalid rows are skipped and reported individually; valid rows are still imported.

---

## Allocation Algorithms

| Algorithm                 | Strategy                                                                 |
|-----------------------------|---------------------------------------------------------------------------|
| First Fit                  | Places each product in the first rack (in configured order) that fits    |
| Best Fit                   | Places each product in the rack with the *least* remaining space that still fits it |
| Worst Fit                  | Places each product in the rack with the *most* remaining space          |
| Priority Based Allocation   | Sorts products by priority (High → Low) before applying First Fit        |
| Space Optimized Allocation  | Sorts products by volume (largest first) and applies Best Fit (decreasing bin-packing) |
| Weight Balanced Allocation  | Always targets the rack with the lowest current weight-utilization ratio, to balance load across racks |

Every strategy respects **rack storage-type compatibility** (Fragile/Cold/Hazardous items only go into matching racks), **volume capacity**, and **weight capacity**. If a product's full quantity cannot fit in one rack, the system automatically splits it across multiple compatible racks; any remainder that cannot be placed is reported as `Partial` or `Unallocated`.

---

## REST API

| Endpoint             | Method | Description                                            |
|----------------------|--------|---------------------------------------------------------|
| `/api/upload`         | POST   | Upload a dataset file, returns parsed dataset + errors  |
| `/api/analyze/<id>`   | GET    | Returns dataset products + AI recommendation             |
| `/api/allocate`        | POST   | Body: `{ "dataset_id": 1, "algorithm": "first_fit" }`     |
| `/api/history`          | GET    | Returns all allocation runs                              |
| `/api/export/<run_id>`   | GET    | Returns full JSON result of a specific run                |
| `/api/racks`              | GET    | Returns current rack configuration                        |

---

## Screenshots

> _Add your own screenshots here after running the app locally:_

- `docs/screenshots/home.png`
- `docs/screenshots/upload.png`
- `docs/screenshots/dashboard.png`
- `docs/screenshots/result.png`
- `docs/screenshots/compare.png`

---

## Troubleshooting

- **`ModuleNotFoundError`** — make sure you activated your virtual environment and ran `pip install -r requirements.txt`.
- **Database looks out of date / corrupted** — stop the app, delete `database.db`, and restart; it will be recreated with default racks.
- **Upload rejected** — only `.txt` files are accepted, and the file must be under 5 MB.
- **"No active racks configured"** on the Dashboard — go to **Upload Dataset → Warehouse Configuration** and make sure at least one rack's *Active* checkbox is ticked.

---

Built with Flask, Bootstrap 5, and Chart.js.
