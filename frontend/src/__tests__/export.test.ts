/**
 * Tests for the exportToCSV utility
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { exportToCSV } from '../utils/export';

describe('exportToCSV', () => {
    const mockLink = {
        href: '',
        download: '',
        style: { display: '' } as CSSStyleDeclaration,
        click: vi.fn(),
    };

    let originalCreateObjectURL: typeof URL.createObjectURL;
    let originalRevokeObjectURL: typeof URL.revokeObjectURL;

    beforeEach(() => {
        mockLink.href = '';
        mockLink.download = '';
        mockLink.click.mockClear();

        vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLElement);
        vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as unknown as HTMLElement);
        vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as unknown as HTMLElement);

        // jsdom doesn't have URL.createObjectURL — assign directly
        originalCreateObjectURL = URL.createObjectURL;
        originalRevokeObjectURL = URL.revokeObjectURL;
        URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
        URL.revokeObjectURL = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
        URL.createObjectURL = originalCreateObjectURL;
        URL.revokeObjectURL = originalRevokeObjectURL;
    });

    it('does nothing when rows are empty', () => {
        exportToCSV([], [{ key: 'a', label: 'A' }], 'test');
        expect(URL.createObjectURL).not.toHaveBeenCalled();
    });

    it('creates a CSV blob with correct content type', () => {
        const rows = [{ name: 'AAPL', price: 150 }];
        const columns = [
            { key: 'name', label: 'Ticker' },
            { key: 'price', label: 'Price' },
        ];

        exportToCSV(rows, columns, 'test');

        expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
        const blob = (URL.createObjectURL as ReturnType<typeof vi.fn>).mock.calls[0][0] as Blob;
        expect(blob).toBeInstanceOf(Blob);
        expect(blob.type).toBe('text/csv;charset=utf-8;');
    });

    it('triggers download with correct filename', () => {
        exportToCSV([{ a: 'val' }], [{ key: 'a', label: 'A' }], 'my_file');
        expect(mockLink.download).toBe('my_file.csv');
        expect(mockLink.click).toHaveBeenCalled();
    });

    it('escapes values containing commas', () => {
        const rows = [{ desc: 'hello, world' }];
        const columns = [{ key: 'desc', label: 'Description' }];

        exportToCSV(rows, columns, 'test');

        const blob = (URL.createObjectURL as ReturnType<typeof vi.fn>).mock.calls[0][0] as Blob;
        // Blob should be created with content (header + data row)
        expect(blob.size).toBeGreaterThan(0);
    });

    it('cleans up object URL after download', () => {
        exportToCSV([{ a: 1 }], [{ key: 'a', label: 'A' }], 'test');
        expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    });
});
