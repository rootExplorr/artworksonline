import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, map, of, tap } from 'rxjs';

interface AdminSession {
  authenticated: boolean;
  username: string;
}

const AUTH_URL = '/api/auth';

@Injectable({ providedIn: 'root' })
export class AdminAuthService {
  private readonly http = inject(HttpClient);
  readonly authenticated = signal(false);
  readonly username = signal<string | null>(null);

  checkSession(): Observable<boolean> {
    return this.http.get<AdminSession>(`${AUTH_URL}/session`, { withCredentials: true }).pipe(
      tap((session) => {
        this.authenticated.set(session.authenticated);
        this.username.set(session.username);
      }),
      map((session) => session.authenticated),
      catchError(() => {
        this.authenticated.set(false);
        this.username.set(null);
        return of(false);
      })
    );
  }

  login(username: string, password: string): Observable<AdminSession> {
    return this.http.post<AdminSession>(
      `${AUTH_URL}/login`,
      { username, password },
      { withCredentials: true }
    ).pipe(tap((session) => {
      this.authenticated.set(session.authenticated);
      this.username.set(session.username);
    }));
  }

  logout(): Observable<void> {
    return this.http.post<void>(`${AUTH_URL}/logout`, {}, { withCredentials: true }).pipe(
      catchError(() => of(undefined)),
      finalize(() => {
        this.authenticated.set(false);
        this.username.set(null);
      })
    );
  }
}