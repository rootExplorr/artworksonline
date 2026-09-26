import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { AdminLogin } from './admin-login';
import { adminGuard } from './admin.guard';
import { AdminAuthService } from './admin-auth.service';
import { ArtworkDetail } from './artwork-detail';
import { ArtworkGallery } from './artwork-gallery';
import { ArtworkManagement } from './artwork-management';
import { ArtworkUpload } from './artwork-upload';
import { routes } from './app.routes';
import { of } from 'rxjs';

describe('artwork routes', () => {
  let httpTesting: HttpTestingController;
  let authService: jasmine.SpyObj<AdminAuthService>;

  beforeEach(async () => {
    authService = jasmine.createSpyObj<AdminAuthService>('AdminAuthService', ['checkSession', 'login', 'logout'], {
      authenticated: signal(false),
      username: signal(null)
    });
    authService.checkSession.and.returnValue(of(false));
    await TestBed.configureTestingModule({
      imports: [AdminLogin, ArtworkDetail, ArtworkGallery, ArtworkManagement, ArtworkUpload],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter(routes),
        { provide: AdminAuthService, useValue: authService }
      ],
    }).compileComponents();
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('keeps browsing and management on separate URLs', () => {
    expect(routes.find((route) => route.path === 'artworks')?.component).toBe(ArtworkGallery);
    expect(routes.find((route) => route.path === 'artworks/:id')?.component).toBe(ArtworkDetail);
    const managementRoute = routes.find((route) => route.path === 'artworks/manage');
    expect(managementRoute?.canActivate).toContain(adminGuard);
    expect(managementRoute?.children?.find((route) => route.path === '')?.component).toBe(ArtworkManagement);
    expect(managementRoute?.children?.find((route) => route.path === 'new')?.component).toBe(ArtworkUpload);
  });

  it('redirects an unauthenticated management visit to login', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/artworks/manage', AdminLogin);

    expect(component).toBeTruthy();
    expect(harness.routeNativeElement?.textContent).toContain('Sign in');
  });

  it('loads and renders artworks without mutation controls', () => {
    const fixture = TestBed.createComponent(ArtworkGallery);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h2')?.textContent).toContain('Works with a point of view');
    httpTesting.expectOne('/api/artworks?sort=price_asc').flush([]);
    fixture.detectChanges();
    expect(compiled.querySelector('form')).toBeNull();
    expect(compiled.querySelector('.delete-button')).toBeNull();
    expect(compiled.textContent).not.toContain('Add the first artwork');
  });

  it('links gallery artworks to their detail page', () => {
    const fixture = TestBed.createComponent(ArtworkGallery);
    fixture.detectChanges();
    httpTesting.expectOne('/api/artworks?sort=price_asc').flush([{
      id: 23,
      title: 'Study in Color',
      description: null,
      price: 100,
      discount_percent: 0,
      final_price: 100,
      image_url: '/uploads/artworks/example.jpg',
      review_count: 2,
      average_rating: 4.5
    }]);
    fixture.detectChanges();

    const link = (fixture.nativeElement as HTMLElement).querySelector('.artwork-card');
    expect(link?.getAttribute('href')).toBe('/artworks/23');
    expect(link?.querySelector('.gallery-rating')?.textContent).toContain('2 reviews');
    expect(link?.querySelector('.gallery-rating')?.textContent).toContain('4.5');
  });

  it('shows the selected artwork on its detail route', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/artworks/23', ArtworkDetail);
    httpTesting.expectOne('/api/artworks/23').flush({
      id: 23,
      title: 'Study in Color',
      description: 'A bright study',
      price: 100,
      discount_percent: 10,
      final_price: 90,
      image_url: '/uploads/artworks/example.jpg',
      review_count: 0,
      average_rating: 0
    });
    httpTesting.expectOne('/api/artworks/23/reviews').flush([]);
    harness.detectChanges();

    expect(component.artwork()?.title).toBe('Study in Color');
    expect(harness.routeNativeElement?.textContent).toContain('A bright study');
  });

  it('persists a submitted rating and refreshes the review count', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/artworks/23', ArtworkDetail);
    const artwork = {
      id: 23,
      title: 'Study in Color',
      description: null,
      price: 100,
      discount_percent: 0,
      final_price: 100,
      image_url: '/uploads/artworks/example.jpg',
      review_count: 0,
      average_rating: 0
    };
    httpTesting.expectOne('/api/artworks/23').flush(artwork);
    httpTesting.expectOne('/api/artworks/23/reviews').flush([]);
    component.reviewForm.controls.reviewer_name.setValue('Sam');
    component.reviewForm.controls.comment.setValue('Lovely use of color.');
    component.selectedRating.set(5);

    component.submitReview();

    const request = httpTesting.expectOne('/api/artworks/23/reviews');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      reviewer_name: 'Sam',
      rating: 5,
      comment: 'Lovely use of color.'
    });
    request.flush({
      id: 9,
      artwork_id: 23,
      reviewer_name: 'Sam',
      rating: 5,
      comment: 'Lovely use of color.',
      created_at: '2026-09-26T12:00:00Z'
    });
    httpTesting.expectOne('/api/artworks/23/reviews').flush([{
      id: 9,
      artwork_id: 23,
      reviewer_name: 'Sam',
      rating: 5,
      comment: 'Lovely use of color.',
      created_at: '2026-09-26T12:00:00Z'
    }]);
    httpTesting.expectOne('/api/artworks/23').flush({
      ...artwork,
      review_count: 1,
      average_rating: 5
    });

    expect(component.artwork()?.review_count).toBe(1);
    expect(component.reviews().length).toBe(1);
  });

  it('shows a not-found state when the detail API has no artwork', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/artworks/999', ArtworkDetail);
    httpTesting.expectOne('/api/artworks/999').flush(
      { detail: 'Artwork not found.' },
      { status: 404, statusText: 'Not Found' }
    );
    harness.detectChanges();

    expect(component.unavailable()).toBeTrue();
    expect(harness.routeNativeElement?.textContent).toContain('Artwork unavailable');
  });

  it('deletes an artwork from the management page after confirmation', () => {
    const fixture = TestBed.createComponent(ArtworkManagement);
    fixture.detectChanges();
    const artwork = {
      id: 17,
      title: 'Study in Color',
      description: null,
      price: 100,
      discount_percent: 0,
      final_price: 100,
      image_url: '/uploads/artworks/example.jpg'
    };
    httpTesting.expectOne('/api/artworks').flush([artwork]);
    spyOn(window, 'confirm').and.returnValue(true);

    fixture.componentInstance.removeArtwork(artwork);

    const deleteRequest = httpTesting.expectOne('/api/artworks/17');
    expect(deleteRequest.request.method).toBe('DELETE');
    deleteRequest.flush(null);
    expect(fixture.componentInstance.artworks()).toEqual([]);
  });

  it('loads an artwork into the edit form', async () => {
    const harness = await RouterTestingHarness.create();
    authService.checkSession.and.returnValue(of(true));
    const navigation = harness.navigateByUrl('/artworks/manage/17/edit', ArtworkUpload);
    const component = await navigation;
    httpTesting.expectOne('/api/artworks/17').flush({
      id: 17,
      title: 'Study in Color',
      description: 'A study',
      price: 100,
      discount_percent: 5,
      final_price: 95,
      image_url: '/uploads/artworks/example.jpg'
    });
    expect(component.editing()).toBeTrue();
    expect(component.uploadForm.controls.title.value).toBe('Study in Color');
  });
});
