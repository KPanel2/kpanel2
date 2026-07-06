import { AuthRequestTraceService } from './auth-request-trace.service';

describe('AuthRequestTraceService', () => {
  let service: AuthRequestTraceService;

  beforeEach(() => {
    service = new AuthRequestTraceService();
  });

  it('starts with no headers recorded', () => {
    expect(service.snapshot()).toEqual({
      authorization: false,
      idToken: false,
      securityFlags: false,
    });
  });

  it('records and snapshots the latest headers', () => {
    service.record({ authorization: true, idToken: true, securityFlags: false });
    expect(service.snapshot()).toEqual({
      authorization: true,
      idToken: true,
      securityFlags: false,
    });
  });

  it('returns a copy from snapshot', () => {
    const snapshot = service.snapshot();
    snapshot.authorization = false;
    expect(service.snapshot().authorization).toBeFalse();
  });

  it('clears recorded headers', () => {
    service.record({ authorization: true, idToken: true, securityFlags: true });
    service.clear();
    expect(service.snapshot()).toEqual({
      authorization: false,
      idToken: false,
      securityFlags: false,
    });
  });
});
