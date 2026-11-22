import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, map, tap } from 'rxjs';

export interface LoginCredentials {
  email: string;
  password: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  readonly accessToken = signal<string | null>(null);
  readonly isAuthenticated = signal(false);
  readonly userEmail = signal<string | null>(null);

  login(credentials: LoginCredentials): Observable<void> {
    return this.http
      .post<TokenResponse>('/api/v1/auth/token', credentials)
      .pipe(
        tap((response) => {
          this.accessToken.set(response.access_token);
          this.isAuthenticated.set(true);
          this.userEmail.set(credentials.email.trim().toLowerCase());
        }),
        map(() => undefined),
      );
  }

  logout(): void {
    this.accessToken.set(null);
    this.isAuthenticated.set(false);
    this.userEmail.set(null);
  }
}
