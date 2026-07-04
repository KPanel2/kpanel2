import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  private devHeaders(): HttpHeaders | undefined {
    const email = localStorage.getItem('kpanel_dev_email');
    if (!email) return undefined;
    return new HttpHeaders({ 'X-KPanel-Dev-Email': email });
  }

  private mergeHeaders(extra?: HttpHeaders): HttpHeaders | undefined {
    const dev = this.devHeaders();
    if (!extra) {
      return dev;
    }
    if (!dev) {
      return extra;
    }

    let merged = dev;
    for (const key of extra.keys()) {
      const value = extra.get(key);
      if (value !== null) {
        merged = merged.set(key, value);
      }
    }
    return merged;
  }

  get<T>(path: string, headers?: HttpHeaders): Observable<T> {
    return this.http
      .get<T>(path, { headers: this.mergeHeaders(headers) })
      .pipe(catchError(this.handleError));
  }

  post<T>(path: string, body: unknown = {}, headers?: HttpHeaders): Observable<T> {
    return this.http
      .post<T>(path, body, { headers: this.mergeHeaders(headers) })
      .pipe(catchError(this.handleError));
  }

  patch<T>(path: string, body: unknown, headers?: HttpHeaders): Observable<T> {
    return this.http
      .patch<T>(path, body, { headers: this.mergeHeaders(headers) })
      .pipe(catchError(this.handleError));
  }

  delete<T>(path: string, body?: unknown, headers?: HttpHeaders): Observable<T> {
    return this.http
      .delete<T>(path, { body, headers: this.mergeHeaders(headers) })
      .pipe(catchError(this.handleError));
  }

  private handleError(err: HttpErrorResponse): Observable<never> {
    const message =
      err.error?.detail || err.error?.message || err.message || 'An unexpected error occurred';
    return throwError(() => new Error(message));
  }
}
