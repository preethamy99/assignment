import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { App } from './app';

describe('App', () => {
  let httpTestingController: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('creates the packing workspace with the sample packages', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance.packages.length).toBe(2);
  });

  it('sends the package list with the bearer token and displays the result', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.apiToken.setValue('test-token');
    app.calculateBoxes();

    const request = httpTestingController.expectOne('/api/v1/pack');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Authorization')).toBe(
      'Bearer test-token',
    );
    expect(request.request.body).toEqual([
      { id: 123, width: 10, height: 10, length: 10, weight: 5 },
      { id: 125, width: 5, height: 5, length: 10, weight: 10 },
    ]);

    request.flush({ box_count: 1 });
    expect(app.result()).toBe(1);
  });

  it('shows an authentication error when the API rejects the token', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.apiToken.setValue('wrong-token');
    app.calculateBoxes();

    httpTestingController.expectOne('/api/v1/pack').flush(
      { detail: 'Invalid or missing bearer token.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(app.errorMessage()).toContain('API token is invalid');
  });
});
