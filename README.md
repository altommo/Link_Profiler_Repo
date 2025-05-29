# Link Profiler System

This project aims to build an open-source link profiler system, inspired by services like Open Link Profiler, with a primary focus on identifying and recovering valuable expired domains. It is designed with a modular architecture, leveraging asynchronous programming (FastAPI, aiohttp) for efficiency.

## Features

*   **Asynchronous Web Crawler:** Efficiently discovers backlinks from specified seed URLs.
*   **Robots.txt & Rate Limiting:** Respects website crawling policies.
*   **Link Extraction & Analysis:** Extracts various link types (dofollow, nofollow, etc.) and their associated anchor text.
*   **Domain Information Retrieval:** Fetches (simulated) WHOIS data and checks domain availability.
*   **Link Profile Generation:** Aggregates backlink data and calculates key metrics (authority, trust, spam scores).
*   **Domain Analysis:** Evaluates domains based on various criteria (age, authority, backlinks) to determine their potential value, especially for expired domains.
*   **Expired Domain Finder:** Searches a list of potential domains for those that are available and deemed valuable.
*   **RESTful API:** Exposes all functionalities via a FastAPI web API.
*   **Simple Data Persistence:** Uses JSON files for data storage (easily swappable for a real database).

## Architecture Overview

The system is structured into several key components:

*   `core/`: Contains core data models (dataclasses) for `Domain`, `URL`, `Backlink`, `LinkProfile`, `CrawlJob`, `CrawlConfig`, and `SEOMetrics`.
*   `crawlers/`: Houses the web crawling logic, including `WebCrawler`, `LinkExtractor`, `ContentParser`, and `RobotsParser`.
*   `database/`: Provides a simple persistence layer using JSON files.
*   `services/`: Contains business logic services:
    *   `CrawlService`: Orchestrates crawling jobs and manages their lifecycle.
    *   `DomainService`: Handles domain-related queries (availability, WHOIS).
    *   `DomainAnalyzerService`: Analyzes domains for their potential value.
    *   `ExpiredDomainFinderService`: Orchestrates the search for valuable expired domains.
*   `api/`: Defines the FastAPI application and its RESTful endpoints.
*   `main.py`: The entry point for running the FastAPI application using Uvicorn.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd link-profiler-system
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create data directory:**
    The `database` module will create a `data/` directory in the project root to store JSON files. Ensure your user has write permissions to the project directory.

## How to Run the API

From the project root directory, run:

