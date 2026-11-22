import { PackageInput } from './package.model';

export const MAX_PACKAGES = 500;
export const MAX_IMPORT_FILE_SIZE_BYTES = 10 * 1024 * 1024;

const REQUIRED_COLUMNS = ['id', 'width', 'height', 'length', 'weight'] as const;
const SUPPORTED_EXTENSIONS = new Set(['csv', 'xls', 'xlsx']);

export class PackageImportError extends Error {}

export function parsePackageRows(rows: unknown[][]): PackageInput[] {
  const headerRowIndex = rows.findIndex((row) =>
    row.some((value) => String(value ?? '').trim() !== ''),
  );
  if (headerRowIndex < 0) {
    throw new PackageImportError('The selected file contains no data.');
  }

  const header = rows[headerRowIndex].map((value) =>
    String(value ?? '')
      .trim()
      .replace(/^\uFEFF/, '')
      .toLowerCase(),
  );
  const columns = REQUIRED_COLUMNS.map((column) => {
    const matches = header
      .map((cell, index) => (cell === column ? index : -1))
      .filter((index) => index >= 0);
    if (matches.length === 0) {
      throw new PackageImportError(`Missing required column: ${column}.`);
    }
    if (matches.length > 1) {
      throw new PackageImportError(`Duplicate column: ${column}.`);
    }
    return matches[0];
  });

  const packages: PackageInput[] = [];
  for (let index = headerRowIndex + 1; index < rows.length; index += 1) {
    const row = rows[index];
    if (row.every((value) => String(value ?? '').trim() === '')) {
      continue;
    }

    const rowNumber = index + 1;
    const [id, width, height, length, weight] = columns.map((columnIndex, i) =>
      parseNumber(row[columnIndex], REQUIRED_COLUMNS[i], rowNumber),
    );

    if (!Number.isSafeInteger(id)) {
      throw new PackageImportError(`Row ${rowNumber}: id must be a whole number.`);
    }
    if (width <= 0 || height <= 0 || length <= 0) {
      throw new PackageImportError(
        `Row ${rowNumber}: width, height, and length must be greater than zero.`,
      );
    }
    if (weight < 0) {
      throw new PackageImportError(`Row ${rowNumber}: weight cannot be negative.`);
    }

    packages.push({ id, width, height, length, weight });
    if (packages.length > MAX_PACKAGES) {
      throw new PackageImportError(
        `A file can contain at most ${MAX_PACKAGES} packages.`,
      );
    }
  }

  if (packages.length === 0) {
    throw new PackageImportError('The selected file contains no package rows.');
  }
  return packages;
}

export async function readPackagesFromFile(file: File): Promise<PackageInput[]> {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    throw new PackageImportError('Choose a .csv, .xls, or .xlsx file.');
  }
  if (file.size > MAX_IMPORT_FILE_SIZE_BYTES) {
    throw new PackageImportError('Files must be 10 MB or smaller.');
  }
  if (file.size === 0) {
    throw new PackageImportError('The selected file is empty.');
  }

  const spreadsheet = await import('@e965/xlsx');
  const workbook = spreadsheet.read(await file.arrayBuffer(), { type: 'array' });
  const firstSheetName = workbook.SheetNames[0];
  const worksheet = firstSheetName ? workbook.Sheets[firstSheetName] : undefined;
  if (!worksheet) {
    throw new PackageImportError('The selected file has no worksheet to import.');
  }

  const rows = spreadsheet.utils.sheet_to_json<unknown[]>(worksheet, {
    header: 1,
    raw: true,
    defval: '',
    blankrows: true,
  });
  return parsePackageRows(rows);
}

function parseNumber(value: unknown, column: string, rowNumber: number): number {
  if (
    (typeof value !== 'number' && typeof value !== 'string') ||
    (typeof value === 'string' && value.trim() === '')
  ) {
    throw new PackageImportError(
      `Row ${rowNumber}: ${column} must contain a number.`,
    );
  }

  const parsed = typeof value === 'number' ? value : Number(value.trim());
  if (!Number.isFinite(parsed)) {
    throw new PackageImportError(
      `Row ${rowNumber}: ${column} must contain a valid number.`,
    );
  }
  return parsed;
}
