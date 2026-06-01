import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  get<T>(path: string): Observable<T> {
    return this.http
      .get<T>(path, { withCredentials: true })
      .pipe(catchError(this.handleError));
  }

  post<T>(path: string, body: unknown = {}): Observable<T> {
    return this.http
      .post<T>(path, body, { withCredentials: true })
      .pipe(catchError(this.handleError));
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http
      .patch<T>(path, body, { withCredentials: true })
      .pipe(catchError(this.handleError));
  }

  delete<T>(path: string, body?: unknown): Observable<T> {
    return this.http
      .delete<T>(path, { withCredentials: true, body })
      .pipe(catchError(this.handleError));
  }

  private handleError(err: HttpErrorResponse): Observable<never> {
    const message =
      err.error?.detail || err.error?.message || err.message || 'An unexpected error occurred';
    return throwError(() => new Error(message));
  }
}
