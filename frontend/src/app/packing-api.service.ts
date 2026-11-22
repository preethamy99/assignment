import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AssistanceRequestInput,
  AssistanceRequestReceipt,
  PackageInput,
  PackingResponse,
} from './package.model';

@Injectable({ providedIn: 'root' })
export class PackingApiService {
  private readonly http = inject(HttpClient);

  calculate(
    packages: PackageInput[],
  ): Observable<PackingResponse> {
    return this.http.post<PackingResponse>('/api/v1/pack', packages);
  }

  createAssistanceRequest(
    request: AssistanceRequestInput,
  ): Observable<AssistanceRequestReceipt> {
    return this.http.post<AssistanceRequestReceipt>(
      '/api/v1/assistance-requests',
      request,
    );
  }
}
