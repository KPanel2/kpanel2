import { HttpClient, HttpErrorResponse, HttpHeaders, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiService } from './api.service';

describe('ApiService', () => {
  let service: ApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.removeItem('kpanel_dev_email');

    TestBed.configureTestingModule({
      providers: [ApiService, provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(ApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.removeItem('kpanel_dev_email');
  });

  it('performs GET requests', () => {
    service.get<{ ok: boolean }>('/api/v1/test').subscribe(response => {
      expect(response.ok).toBeTrue();
    });

    const req = httpMock.expectOne('/api/v1/test');
    expect(req.request.method).toBe('GET');
    req.flush({ ok: true });
  });

  it('performs POST requests with a default body', () => {
    service.post('/api/v1/test').subscribe();
    const req = httpMock.expectOne('/api/v1/test');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({});
  });

  it('performs PATCH and DELETE requests', () => {
    service.patch('/api/v1/test', { name: 'x' }).subscribe();
    httpMock.expectOne('/api/v1/test').flush({});

    service.delete('/api/v1/test', { force: true }).subscribe();
    const deleteReq = httpMock.expectOne('/api/v1/test');
    expect(deleteReq.request.method).toBe('DELETE');
    expect(deleteReq.request.body).toEqual({ force: true });
    deleteReq.flush({});
  });

  it('merges dev auth headers from localStorage', () => {
    localStorage.setItem('kpanel_dev_email', 'dev@example.com');
    const extra = new HttpHeaders({ 'X-Custom': 'yes' });

    service.get('/api/v1/test', extra).subscribe();
    const req = httpMock.expectOne('/api/v1/test');
    expect(req.request.headers.get('X-KPanel-Dev-Email')).toBe('dev@example.com');
    expect(req.request.headers.get('X-Custom')).toBe('yes');
    req.flush({});
  });

  it('maps HTTP errors to Error with detail/message', () => {
    let message = '';
    service.get('/api/v1/test').subscribe({
      error: (err: Error) => {
        message = err.message;
      },
    });

    httpMock.expectOne('/api/v1/test').flush(
      { detail: 'Not allowed' },
      { status: 403, statusText: 'Forbidden' },
    );
    expect(message).toBe('Not allowed');
  });

  it('uses only extra headers when dev email is absent', () => {
    const extra = new HttpHeaders({ 'X-Custom': 'yes' });

    service.get('/api/v1/test', extra).subscribe();
    const req = httpMock.expectOne('/api/v1/test');
    expect(req.request.headers.get('X-Custom')).toBe('yes');
    expect(req.request.headers.has('X-KPanel-Dev-Email')).toBeFalse();
    req.flush({});
  });

  it('maps HTTP errors using error.message', () => {
    let message = '';
    service.get('/api/v1/test').subscribe({
      error: (err: Error) => {
        message = err.message;
      },
    });

    httpMock.expectOne('/api/v1/test').flush(
      { message: 'Validation failed' },
      { status: 400, statusText: 'Bad Request' },
    );
    expect(message).toBe('Validation failed');
  });

  it('falls back to generic error message', () => {
    let message = '';
    service.get('/api/v1/test').subscribe({
      error: (err: Error) => {
        message = err.message;
      },
    });

    httpMock.expectOne('/api/v1/test').error(
      new ProgressEvent('error'),
      { status: 0, statusText: 'Unknown' },
    );
    expect(message).toBeTruthy();
  });
});
