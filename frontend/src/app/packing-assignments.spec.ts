import { buildAssignmentsCsv } from './packing-assignments';
import { PackedBox } from './package.model';

describe('buildAssignmentsCsv', () => {
  it('exports box details and each package from the backend assignment', () => {
    const boxes: PackedBox[] = [
      {
        box_number: 1,
        box_type: 'B',
        width: 100,
        height: 200,
        length: 100,
        max_weight: 1000,
        total_weight: 15,
        packages: [
          { id: 123, width: 10, height: 10, length: 10, weight: 5 },
          { id: 125, width: 5, height: 5, length: 10, weight: 10 },
        ],
      },
    ];

    expect(buildAssignmentsCsv(boxes)).toBe(
      [
        'box_number,box_type,box_width,box_height,box_length,box_max_weight,box_total_weight,package_id,package_width,package_height,package_length,package_weight',
        '1,B,100,200,100,1000,15,123,10,10,10,5',
        '1,B,100,200,100,1000,15,125,5,5,10,10',
      ].join('\r\n'),
    );
  });
});
