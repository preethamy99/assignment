import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { PackageInput, PackingResponse } from './package.model';

@Injectable({ providedIn: 'root' })
export class PackingApiService {
  private readonly http = inject(HttpClient);

  calculate(
    packages: PackageInput[],
    apiToken: string,
  ): Observable<PackingResponse> {
    return this.http.post<PackingResponse>('/api/v1/pack', packages, {
      headers: new HttpHeaders({
        Authorization: `Bearer ${apiToken}`,
      }),
    });
  }
}
