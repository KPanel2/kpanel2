import { KumpeAccountCenterService } from './kumpe-account-center.service';
import { environment } from '../../../environments/environment';

describe('KumpeAccountCenterService', () => {
  let service: KumpeAccountCenterService;
  let originalEndpoint: string;

  beforeEach(() => {
    originalEndpoint = environment.logto.endpoint;
    environment.logto.endpoint = 'https://auth.example.com/';
    service = new KumpeAccountCenterService();
    history.replaceState({}, '', '/dashboard?tab=profile#section');
  });

  afterEach(() => {
    environment.logto.endpoint = originalEndpoint;
  });

  it('builds profile and security URLs with default redirect', () => {
    const profile = new URL(service.profileUrl());
    const security = new URL(service.securityUrl());
    expect(profile.origin).toBe('https://auth.example.com');
    expect(profile.pathname).toBe('/account/profile');
    expect(security.pathname).toBe('/account/security');
    expect(profile.searchParams.get('redirect')).toContain('/dashboard');
    expect(profile.searchParams.get('redirect')).not.toContain('?');
  });

  it('builds email, password, and username URLs', () => {
    expect(new URL(service.emailUrl()).pathname).toBe('/account/email');
    expect(new URL(service.passwordUrl()).pathname).toBe('/account/password');
    expect(new URL(service.usernameUrl()).pathname).toBe('/account/username');
  });

  it('supports custom redirect and show_success', () => {
    const url = new URL(service.buildUrl('account/security', {
      redirectUrl: 'https://panel.example/settings',
      showSuccess: true,
    }));
    expect(url.pathname).toBe('/account/security');
    expect(url.searchParams.get('redirect')).toBe('https://panel.example/settings');
    expect(url.searchParams.get('show_success')).toBe('true');
  });

  it('normalizes relative paths without a leading slash', () => {
    const url = new URL(service.buildUrl('account/email'));
    expect(url.pathname).toBe('/account/email');
  });
});
