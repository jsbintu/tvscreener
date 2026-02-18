/**
 * DataTable — Generic sortable data table with premium styling
 *
 * Usage:
 *   <DataTable
 *     columns={[
 *       { key: 'ticker', label: 'Ticker', sortable: true },
 *       { key: 'price', label: 'Price', sortable: true, align: 'right' },
 *     ]}
 *     rows={data}
 *     onRowClick={(row) => navigate(`/stock/${row.ticker}`)}
 *     sortKey="price"
 *     sortDir="desc"
 *     onSort={(key) => handleSort(key)}
 *   />
 */

import { ChevronDown, ChevronUp } from 'lucide-react';
import type React from 'react';

/* eslint-disable @typescript-eslint/no-explicit-any */

export interface Column {
    key: string;
    label: string;
    sortable?: boolean;
    align?: 'left' | 'center' | 'right';
    render?: (value: any, row: any) => React.ReactNode;
    width?: string;
}

interface DataTableProps {
    columns: Column[];
    rows: any[];
    sortKey?: string;
    sortDir?: 'asc' | 'desc';
    onSort?: (key: string) => void;
    onRowClick?: (row: any) => void;
    emptyText?: string;
    stickyHeader?: boolean;
}

const DataTable: React.FC<DataTableProps> = ({
    columns,
    rows,
    sortKey,
    sortDir,
    onSort,
    onRowClick,
    emptyText = 'No data available',
    stickyHeader = false,
}) => {
    return (
        <div className="data-table-wrap" style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                    <tr>
                        {columns.map((col) => (
                            <th
                                key={col.key}
                                onClick={col.sortable && onSort ? () => onSort(col.key) : undefined}
                                style={{
                                    textAlign: col.align || 'left',
                                    cursor: col.sortable ? 'pointer' : 'default',
                                    padding: '10px 12px',
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    color: 'var(--text-muted)',
                                    borderBottom: '1px solid var(--glass-border)',
                                    whiteSpace: 'nowrap',
                                    userSelect: 'none',
                                    width: col.width,
                                    position: stickyHeader ? 'sticky' : undefined,
                                    top: stickyHeader ? 0 : undefined,
                                    background: stickyHeader ? 'var(--bg-card)' : undefined,
                                    zIndex: stickyHeader ? 1 : undefined,
                                }}
                            >
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                    {col.label}
                                    {col.sortable &&
                                        sortKey === col.key &&
                                        (sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
                                </span>
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 ? (
                        <tr>
                            <td
                                colSpan={columns.length}
                                style={{
                                    padding: '32px',
                                    textAlign: 'center',
                                    color: 'var(--text-muted)',
                                    fontSize: '14px',
                                }}
                            >
                                {emptyText}
                            </td>
                        </tr>
                    ) : (
                        rows.map((row, rowIdx) => (
                            <tr
                                key={rowIdx}
                                onClick={onRowClick ? () => onRowClick(row) : undefined}
                                style={{
                                    cursor: onRowClick ? 'pointer' : 'default',
                                    transition: 'background var(--transition-fast)',
                                }}
                                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                                onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                            >
                                {columns.map((col) => (
                                    <td
                                        key={col.key}
                                        style={{
                                            padding: '10px 12px',
                                            fontSize: '13px',
                                            color: 'var(--text-primary)',
                                            borderBottom: '1px solid var(--glass-border)',
                                            textAlign: col.align || 'left',
                                            fontFamily: col.align === 'right' ? 'var(--font-mono)' : undefined,
                                        }}
                                    >
                                        {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                                    </td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
};

export default DataTable;
