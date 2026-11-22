export interface PackageInput {
  id: number;
  width: number;
  height: number;
  length: number;
  weight: number;
  fragile?: boolean;
}

export type BoxType = 'A' | 'B' | 'C';
export type SpecialHandlingReason = 'fragile' | 'oversized' | 'overweight';

export interface PackedPackage extends PackageInput {
  fragile: boolean;
}

export interface PackedBox {
  box_number: number;
  box_type: BoxType;
  width: number;
  height: number;
  length: number;
  max_weight: number;
  total_weight: number;
  packages: PackedPackage[];
}

export interface SpecialHandlingItem extends PackageInput {
  fragile: boolean;
  reasons: SpecialHandlingReason[];
}

export interface PackingResponse {
  box_count: number;
  boxes: PackedBox[];
  special_handling_required: boolean;
  special_items: SpecialHandlingItem[];
}

export interface AssistanceRequestInput {
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  notes: string;
  packages: PackageInput[];
}

export interface AssistanceRequestReceipt {
  request_id: string;
  submitted_at: string;
  status: 'submitted';
}
