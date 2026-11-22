import { PackedBox } from './package.model';

const CSV_HEADERS = [
  'box_number',
  'box_type',
  'box_width',
  'box_height',
  'box_length',
  'box_max_weight',
  'box_total_weight',
  'package_id',
  'package_width',
  'package_height',
  'package_length',
  'package_weight',
];

export function buildAssignmentsCsv(boxes: PackedBox[]): string {
  const rows = boxes.flatMap((box) =>
    box.packages.map((item) => [
      box.box_number,
      box.box_type,
      box.width,
      box.height,
      box.length,
      box.max_weight,
      box.total_weight,
      item.id,
      item.width,
      item.height,
      item.length,
      item.weight,
    ]),
  );
  return [CSV_HEADERS, ...rows].map((row) => row.map(escapeCsvValue).join(',')).join('\r\n');
}

function escapeCsvValue(value: string | number): string {
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
