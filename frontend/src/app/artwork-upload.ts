import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

interface Artwork {
  id: number;
  title: string;
  description: string | null;
  price: number;
  discount_percent: number;
  image_url: string;
}

const API_URL = '/api/artworks';
const API_ORIGIN = '';

@Component({
  selector: 'app-artwork-upload',
  imports: [
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    ReactiveFormsModule,
    RouterLink
  ],
  templateUrl: './artwork-upload.html'
})
export class ArtworkUpload implements OnInit, OnDestroy {
  private readonly http = inject(HttpClient);
  private readonly formBuilder = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private previewUrl: string | null = null;

  readonly uploading = signal(false);
  readonly loadingArtwork = signal(false);
  readonly editing = signal(false);
  readonly selectedFile = signal<File | null>(null);
  readonly imagePreview = signal<string | null>(null);
  readonly currentImageUrl = signal<string | null>(null);
  private artworkId: number | null = null;

  readonly uploadForm = this.formBuilder.group({
    title: ['', [Validators.required, Validators.maxLength(120)]],
    description: ['', Validators.maxLength(1000)],
    price: [null as number | null, [Validators.required, Validators.min(0.01)]],
    discount_percent: [0, [Validators.min(0), Validators.max(100)]]
  });

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam === null) {
      return;
    }

    const id = Number(idParam);
    if (!Number.isInteger(id) || id < 1) {
      void this.router.navigateByUrl('/artworks/manage');
      return;
    }

    this.artworkId = id;
    this.editing.set(true);
    this.loadingArtwork.set(true);
    this.http.get<Artwork>(`${API_URL}/${id}`).subscribe({
      next: (artwork) => {
        this.uploadForm.patchValue({
          title: artwork.title,
          description: artwork.description ?? '',
          price: artwork.price,
          discount_percent: artwork.discount_percent
        });
        this.currentImageUrl.set(`${API_ORIGIN}${artwork.image_url}`);
        this.loadingArtwork.set(false);
      },
      error: () => {
        this.loadingArtwork.set(false);
        this.snackBar.open('Could not load this artwork.', 'Dismiss', { duration: 4000 });
        void this.router.navigateByUrl('/artworks/manage');
      }
    });
  }

  ngOnDestroy(): void {
    this.revokePreview();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.revokePreview();
    this.selectedFile.set(file);
    if (file) {
      this.previewUrl = URL.createObjectURL(file);
      this.imagePreview.set(this.previewUrl);
    }
  }

  submitUpload(): void {
    const file = this.selectedFile();
    if (this.uploadForm.invalid || (!file && !this.editing()) || this.uploading() || this.loadingArtwork()) {
      this.uploadForm.markAllAsTouched();
      return;
    }

    const values = this.uploadForm.getRawValue();
    const data = new FormData();
    data.append('title', values.title?.trim() ?? '');
    data.append('description', values.description?.trim() ?? '');
    data.append('price', String(values.price));
    data.append('discount_percent', String(values.discount_percent ?? 0));
    if (file) {
      data.append('image', file);
    }

    this.uploading.set(true);
    const request = this.editing()
      ? this.http.put<Artwork>(`${API_URL}/${this.artworkId}`, data)
      : this.http.post<Artwork>(API_URL, data);
    request.subscribe({
      next: () => {
        this.uploading.set(false);
        this.snackBar.open(this.editing() ? 'Artwork updated.' : 'Artwork added.', 'Dismiss', { duration: 3000 });
        void this.router.navigateByUrl('/artworks/manage');
      },
      error: (response) => {
        this.uploading.set(false);
        const message = response.error?.detail ?? 'Artwork could not be uploaded.';
        this.snackBar.open(message, 'Dismiss', { duration: 5000 });
      }
    });
  }

  private revokePreview(): void {
    if (this.previewUrl) {
      URL.revokeObjectURL(this.previewUrl);
      this.previewUrl = null;
    }
    this.imagePreview.set(null);
  }

  imageSource(path: string): string {
    return `${API_ORIGIN}${path}`;
  }
}