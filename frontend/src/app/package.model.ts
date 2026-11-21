export interface PackageInput {
  id: number;
  width: number;
  height: number;
  length: number;
  weight: number;
}

export interface PackingResponse {
  box_count: number;
}
