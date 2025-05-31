"""
Data Exporter - Provides utilities for exporting data to various formats.
File: Link_Profiler/utils/data_exporter.py
"""

import csv
import io
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

async def export_to_csv(data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> io.StringIO:
    """
    Exports a list of dictionaries to a CSV formatted StringIO object.

    Args:
        data: A list of dictionaries, where each dictionary represents a row.
        fieldnames: An optional list of column headers. If not provided,
                    it will be inferred from the keys of the first dictionary.

    Returns:
        A StringIO object containing the CSV data.
    """
    if not data:
        logger.warning("No data provided for CSV export.")
        output = io.StringIO()
        if fieldnames:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
        return output

    if fieldnames is None:
        # Infer fieldnames from the keys of all dictionaries to ensure all columns are captured
        all_keys = set()
        for row in data:
            all_keys.update(row.keys())
        fieldnames = sorted(list(all_keys)) # Sort for consistent column order

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)

    writer.writeheader()
    for row in data:
        # Filter row to only include keys present in fieldnames, and handle missing keys
        filtered_row = {k: row.get(k, '') for k in fieldnames}
        writer.writerow(filtered_row)

    output.seek(0)
    logger.info(f"Exported {len(data)} records to CSV.")
    return output
