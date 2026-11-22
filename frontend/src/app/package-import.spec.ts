import { describe, expect, it } from 'vitest';
import * as XLSX from '@e965/xlsx';

import {
  PackageImportError,
  parsePackageRows,
  readPackagesFromFile,
} from './package-import';

describe('parsePackageRows', () => {
  it('maps case-insensitive columns in any order and skips blank rows', () => {
    const packages = parsePackageRows([
      [' LENGTH ', 'ID', 'Weight', 'WIDTH', 'Height'],
      ['30', '8', '0', '10', '20'],
      ['', '', '', '', ''],
    ]);

    expect(packages).toEqual([
      {
        id: 8,
        width: 10,
        height: 20,
        length: 30,
        weight: 0,
        fragile: false,
      },
    ]);
  });

  it('accepts a fragile column with common true/false values', () => {
    expect(
      parsePackageRows([
        ['id', 'width', 'height', 'length', 'weight', 'fragile'],
        [1, 10, 10, 10, 5, 'glass'],
        [2, 10, 10, 10, 5, 'no'],
        [3, 10, 10, 10, 5, '  '],
      ]),
    ).toEqual([
      { id: 1, width: 10, height: 10, length: 10, weight: 5, fragile: true },
      { id: 2, width: 10, height: 10, length: 10, weight: 5, fragile: false },
      { id: 3, width: 10, height: 10, length: 10, weight: 5, fragile: false },
    ]);
  });

  it('rejects invalid fragile column values', () => {
    expect(() =>
      parsePackageRows([
        ['id', 'width', 'height', 'length', 'weight', 'fragile'],
        [1, 10, 10, 10, 5, 'maybe'],
      ]),
    ).toThrow('Row 2: fragile must be true or false.');
  });

  it('rejects files that are missing a required column', () => {
    expect(() =>
      parsePackageRows([['id', 'width', 'height', 'length'], [1, 10, 10, 10]]),
    ).toThrow('Missing required column: weight.');
  });

  it('reports the spreadsheet row for invalid package values', () => {
    expect(() =>
      parsePackageRows([
        ['id', 'width', 'height', 'length', 'weight'],
        [1, 10, 0, 10, 5],
      ]),
    ).toThrow('Row 2: width, height, and length must be greater than zero.');
  });

  it('rejects package rows with negative weight', () => {
    expect(() =>
      parsePackageRows([
        ['id', 'width', 'height', 'length', 'weight'],
        [1, 10, 10, 10, -1],
      ]),
    ).toThrow('Row 2: weight cannot be negative.');
  });

  it('rejects files with more than 500 package rows', () => {
    const rows: unknown[][] = [
      ['id', 'width', 'height', 'length', 'weight'],
      ...Array.from({ length: 501 }, (_, index) => [
        index + 1,
        1,
        1,
        1,
        1,
      ]),
    ];
    expect(() => parsePackageRows(rows)).toThrow(
      'A file can contain at most 500 packages.',
    );
  });
});

describe('readPackagesFromFile', () => {
  it('reads CSV package rows', async () => {
    const file = new File(
      ['id,width,height,length,weight\n7,10,20,30,4'],
      'packages.csv',
      { type: 'text/csv' },
    );

    await expect(readPackagesFromFile(file)).resolves.toEqual([
      { id: 7, width: 10, height: 20, length: 30, weight: 4, fragile: false },
    ]);
  });

  it('rejects unsupported file types', async () => {
    const file = new File(['data'], 'packages.txt');
    await expect(readPackagesFromFile(file)).rejects.toBeInstanceOf(
      PackageImportError,
    );
  });

  it.each(['xls', 'xlsx'] as const)('reads Excel .%s workbooks', async (extension) => {
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.aoa_to_sheet([
      ['id', 'width', 'height', 'length', 'weight'],
      [9, 15, 20, 25, 30],
    ]);
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Packages');
    const fileContents = XLSX.write(workbook, {
      bookType: extension,
      type: 'array',
    });
    const file = new File([fileContents], `packages.${extension}`);

    await expect(readPackagesFromFile(file)).resolves.toEqual([
      {
        id: 9,
        width: 15,
        height: 20,
        length: 25,
        weight: 30,
        fragile: false,
      },
    ]);
  });
});
