import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DataTable from '../components/Data/DataTable';

describe('DataTable', () => {
    const columns = [
        { key: 'name', label: 'Name', sortable: true },
        { key: 'price', label: 'Price', sortable: true, align: 'right' as const },
        { key: 'change', label: 'Change', sortable: true, align: 'right' as const },
    ];

    const rows = [
        { name: 'AAPL', price: 195.23, change: 2.5 },
        { name: 'MSFT', price: 420.1, change: -1.2 },
        { name: 'GOOGL', price: 175.88, change: 0.8 },
    ];

    it('renders column headers', () => {
        render(<DataTable columns={columns} rows={rows} />);
        expect(screen.getByText('Name')).toBeInTheDocument();
        expect(screen.getByText('Price')).toBeInTheDocument();
        expect(screen.getByText('Change')).toBeInTheDocument();
    });

    it('renders data rows', () => {
        render(<DataTable columns={columns} rows={rows} />);
        expect(screen.getByText('AAPL')).toBeInTheDocument();
        expect(screen.getByText('MSFT')).toBeInTheDocument();
        expect(screen.getByText('GOOGL')).toBeInTheDocument();
    });

    it('renders empty state', () => {
        render(<DataTable columns={columns} rows={[]} />);
        expect(screen.getByText(/no data/i)).toBeInTheDocument();
    });

    it('renders custom empty text', () => {
        render(<DataTable columns={columns} rows={[]} emptyText="Nothing here" />);
        expect(screen.getByText('Nothing here')).toBeInTheDocument();
    });

    it('calls onRowClick when a row is clicked', () => {
        const handleClick = vi.fn();
        render(<DataTable columns={columns} rows={rows} onRowClick={handleClick} />);

        const row = screen.getByText('AAPL').closest('tr');
        if (row) fireEvent.click(row);

        expect(handleClick).toHaveBeenCalledWith(rows[0]);
    });

    it('calls onSort when a sortable header is clicked', () => {
        const handleSort = vi.fn();
        render(<DataTable columns={columns} rows={rows} onSort={handleSort} />);

        fireEvent.click(screen.getByText('Name'));
        expect(handleSort).toHaveBeenCalledWith('name');
    });

    it('renders all row values', () => {
        render(<DataTable columns={columns} rows={rows} />);
        expect(screen.getByText('195.23')).toBeInTheDocument();
        expect(screen.getByText('420.1')).toBeInTheDocument();
    });
});
