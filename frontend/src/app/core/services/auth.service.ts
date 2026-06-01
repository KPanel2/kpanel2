import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { ApiService } from './api.service';
import { SessionState, User } from '../models/session.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _session = new BehaviorSubject<SessionState | null>(null);
  session$: Observable<SessionState | null> = this._session.asObservable();

  constructor(private api: ApiService) {}

  get snapshot(): SessionState | null {
    return this._session.value;
  }

  get isAuthenticated(): boolean {
    return this._session.value?.status === 'authenticated';
  }

  get currentUser(): User | undefined {
    return this._session.value?.user;
  }

  loadSession(): Observable<SessionState> {
    return this.api.get<SessionState>('/api/v1/auth/session').pipe(
      tap(session => this._session.next(session))
    );
  }

  logout(): Observable<unknown> {
    return this.api.post('/api/v1/auth/logout').pipe(
      tap(() => this._session.next(null))
    );
  }

  createAccount(displayName: string, timezone: string): Observable<unknown> {
    return this.api.post('/api/v1/account/create', { display_name: displayName, timezone });
  }

  completeLink(): Observable<unknown> {
    return this.api.post('/api/v1/account/link/complete');
  }

  updateProfile(displayName: string, timezone: string): Observable<User> {
    return this.api.patch<User>('/api/v1/account/profile', {
      display_name: displayName,
      timezone,
    });
  }
}
