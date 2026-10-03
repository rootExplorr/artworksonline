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
  images: ArtworkImage[];
}

interface ArtworkImage {
  id: number;
  image_url: string;
  position: number;
}

interface SelectedImage {
  file: File;
  previewUrl: string;
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
  templateUrl: './artwork-upload.html',
  styleUrl: './artwork-upload.scss'
})
export class ArtworkUpload implements OnInit, OnDestroy {
  private readonly http = inject(HttpClient);
  private readonly formBuilder = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private previewUrls: string[] = [];

  readonly uploading = signal(false);
  readonly loadingArtwork = signal(false);
  readonly editing = signal(false);
  readonly selectedImages = signal<SelectedImage[]>([]);
  readonly currentImages = signal<ArtworkImage[]>([]);
  readonly removingImageId = signal<number | null>(null);
  readonly maxImages = 10;
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
        this.currentImages.set(artwork.images ?? []);
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
    this.revokePreviews();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    const availableSlots = this.maxImages - this.currentImages().length;
    if (files.length > availableSlots) {
      this.snackBar.open(
        availableSlots === 0
          ? `This artwork already has the maximum of ${this.maxImages} images.`
          : `You can add ${availableSlots} more ${availableSlots === 1 ? 'image' : 'images'}.`,
        'Dismiss',
        { duration: 4000 }
      );
      return;
    }

    this.revokePreviews();
    const previews = files.map((file) => ({
      file,
      previewUrl: URL.createObjectURL(file)
    }));
    this.previewUrls = previews.map((preview) => preview.previewUrl);
    this.selectedImages.set(previews);
  }

  removeSelectedImage(previewUrl: string): void {
    URL.revokeObjectURL(previewUrl);
    this.previewUrls = this.previewUrls.filter((url) => url !== previewUrl);
    this.selectedImages.update((images) => images.filter((image) => image.previewUrl !== previewUrl));
  }

  removeCurrentImage(image: ArtworkImage): void {
    if (this.currentImages().length <= 1 || this.removingImageId() !== null || this.artworkId === null) {
      return;
    }

    this.removingImageId.set(image.id);
    this.http.delete<void>(`${API_URL}/${this.artworkId}/images/${image.id}`).subscribe({
      next: () => {
        this.currentImages.update((images) => images.filter((current) => current.id !== image.id));
        this.removingImageId.set(null);
        this.snackBar.open('Image removed.', 'Dismiss', { duration: 3000 });
      },
      error: (response) => {
        this.removingImageId.set(null);
        const message = response.error?.detail ?? 'Image could not be removed.';
        this.snackBar.open(message, 'Dismiss', { duration: 5000 });
      }
    });
  }

  submitUpload(): void {
    if (
      this.uploadForm.invalid ||
      (!this.selectedImages().length && !this.editing()) ||
      this.uploading() ||
      this.loadingArtwork()
    ) {
      this.uploadForm.markAllAsTouched();
      return;
    }

    const values = this.uploadForm.getRawValue();
    const data = new FormData();
    data.append('title', values.title?.trim() ?? '');
    data.append('description', values.description?.trim() ?? '');
    data.append('price', String(values.price));
    data.append('discount_percent', String(values.discount_percent ?? 0));
    for (const image of this.selectedImages()) {
      data.append('images', image.file);
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

  private revokePreviews(): void {
    for (const url of this.previewUrls) {
      URL.revokeObjectURL(url);
    }
    this.previewUrls = [];
    this.selectedImages.set([]);
  }

  imageSource(path: string): string {
    return `${API_ORIGIN}${path}`;
  }
}