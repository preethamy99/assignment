export interface PackageInput {
  id: number;
  width: number;
  height: number;
  length: number;
  weight: number;
}

export type BoxType = 'A' | 'B' | 'C';

export interface PackedBox {
  box_number: number;
  box_type: BoxType;
  width: number;
  height: number;
  length: number;
  max_weight: number;
  total_weight: number;
  packages: PackageInput[];
}

export interface PackingResponse {
  box_count: number;
  boxes: PackedBox[];
}
