import {
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { App } from './app';
import { authInterceptor } from './auth.interceptor';

describe('App', () => {
  let httpTestingController: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('creates the sign-in view and sample packages', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance.packages.length).toBe(2);
    expect(fixture.componentInstance.auth.isAuthenticated()).toBe(false);
  });

  it('fetches a JWT then attaches it to packing requests automatically', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.loginForm.controls.password.setValue('test-password');
    app.login();

    const loginRequest = httpTestingController.expectOne('/api/v1/auth/token');
    expect(loginRequest.request.method).toBe('POST');
    expect(loginRequest.request.body).toEqual({
      email: 'test@example.com',
      password: 'test-password',
    });
    loginRequest.flush({
      access_token: 'signed-test-token',
      token_type: 'bearer',
    });

    app.calculateBoxes();

    const request = httpTestingController.expectOne('/api/v1/pack');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Authorization')).toBe(
      'Bearer signed-test-token',
    );
    expect(request.request.body).toEqual([
      { id: 123, width: 10, height: 10, length: 10, weight: 5 },
      { id: 125, width: 5, height: 5, length: 10, weight: 10 },
    ]);

    request.flush({
      box_count: 1,
      boxes: [
        {
          box_number: 1,
          box_type: 'B',
          width: 100,
          height: 200,
          length: 100,
          max_weight: 1000,
          total_weight: 15,
          packages: [
            { id: 123, width: 10, height: 10, length: 10, weight: 5 },
            { id: 125, width: 5, height: 5, length: 10, weight: 10 },
          ],
        },
      ],
    });
    expect(app.result()).toBe(1);
    expect(app.boxes()[0].box_type).toBe('B');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Items by box');
    expect(fixture.nativeElement.textContent).toContain('Package #123');
  });

  it('shows an authentication error when login credentials are rejected', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.loginForm.controls.password.setValue('wrong-password');
    app.login();

    httpTestingController.expectOne('/api/v1/auth/token').flush(
      { detail: 'Invalid email or password.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(app.errorMessage()).toContain('Email or password is incorrect');
  });
});
