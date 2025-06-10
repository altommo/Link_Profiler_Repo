# Link Profiler API Reference

This document outlines the architecture and usage of the Link Profiler customer-facing APIs, focusing on the recent enhancements for performance, reliability, and tiered access.

## 1. Cache-First Architecture Overview

To ensure sub-second response times and predictable performance, all customer-facing API endpoints now operate on a **cache-first** principle by default. This means that when you make a request, the API will first attempt to serve the data from a highly optimised, frequently updated cache.

**Benefits:**
*   **Speed:** Most requests will be served from cache, resulting in significantly faster response times (typically sub-second).
*   **Reliability:** Cached data provides consistent performance, reducing dependency on the real-time availability of external data sources.
*   **Efficiency:** Reduces the load on external APIs and our internal processing systems.

Our cache is regularly updated (typically every 15-30 minutes, depending on the data type) to ensure data freshness.

## 2. Live Data Access

While cached data is suitable for most use cases, we understand that real-time data is sometimes critical. For such scenarios, you can explicitly request **live data** using the `source=live` query parameter.

**Requesting Live Data:**
To request live data, append `?source=live` to your API call:

