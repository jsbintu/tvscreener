/**
 * CSV Export utility
 *
 * Generates a CSV file and triggers browser download.
 */

interface Column {
    key: string;
    label: string;
}

function escapeCSV(value: unknown): string {
    const str = String(value ?? '');
    // Wrap in quotes if contains commas, quotes, or newlines
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
}

export function exportToCSV(rows: Record<string, unknown>[], columns: Column[], filename: string): void {
    if (rows.length === 0) return;

    // Header row
    const header = columns.map((c) => escapeCSV(c.label)).join(',');

    // Data rows
    const body = rows.map((row) => columns.map((c) => escapeCSV(row[c.key])).join(',')).join('\n');

    const csv = `${header}\n${body}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.csv`;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
