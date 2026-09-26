import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ActivatedRoute, RouterLink } from '@angular/router';

interface Artwork {
  id: number;
  title: string;
  description: string | null;
  price: number;
  discount_percent: number;
  final_price: number;
  image_url: string;
  review_count: number;
  average_rating: number;
}

interface ArtworkReview {
  id: number;
  artwork_id: number;
  reviewer_name: string | null;
  rating: number;
  comment: string;
  created_at: string;
}

const API_URL = '/api/artworks';
const API_ORIGIN = '';

@Component({
  selector: 'app-artwork-detail',
  imports: [
    CurrencyPipe,
    DatePipe,
    DecimalPipe,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    ReactiveFormsModule,
    RouterLink
  ],
  templateUrl: './artwork-detail.html',
  styleUrl: './artwork-detail.scss'
})
export class ArtworkDetail implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly formBuilder = inject(FormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  readonly artwork = signal<Artwork | null>(null);
  readonly reviews = signal<ArtworkReview[]>([]);
  readonly loading = signal(true);
  readonly unavailable = signal(false);
  readonly reviewsLoading = signal(true);
  readonly submittingReview = signal(false);
  readonly selectedRating = signal(0);
  readonly starValues = [1, 2, 3, 4, 5];

  readonly reviewForm = this.formBuilder.group({
    reviewer_name: ['', Validators.maxLength(80)],
    comment: ['', [Validators.required, Validators.maxLength(2000)]]
  });

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (!Number.isInteger(id) || id < 1) {
      this.loading.set(false);
      this.unavailable.set(true);
      return;
    }

    this.http.get<Artwork>(`${API_URL}/${id}`).subscribe({
      next: (artwork) => {
        this.artwork.set(artwork);
        this.loading.set(false);
        this.loadReviews(artwork.id);
      },
      error: () => {
        this.loading.set(false);
        this.unavailable.set(true);
      }
    });
  }

  imageSource(path: string): string {
    return `${API_ORIGIN}${path}`;
  }

  loadReviews(artworkId: number): void {
    this.reviewsLoading.set(true);
    this.http.get<ArtworkReview[]>(`${API_URL}/${artworkId}/reviews`).subscribe({
      next: (reviews) => {
        this.reviews.set(reviews);
        this.reviewsLoading.set(false);
      },
      error: () => {
        this.reviews.set([]);
        this.reviewsLoading.set(false);
        this.snackBar.open('Could not load reviews.', 'Dismiss', { duration: 4000 });
      }
    });
  }

  submitReview(): void {
    const artwork = this.artwork();
    const rating = this.selectedRating();
    if (!artwork || this.reviewForm.invalid || rating < 1 || this.submittingReview() || this.reviewsLoading()) {
      this.reviewForm.markAllAsTouched();
      return;
    }

    const values = this.reviewForm.getRawValue();
    this.submittingReview.set(true);
    this.http.post<ArtworkReview>(`${API_URL}/${artwork.id}/reviews`, {
      reviewer_name: values.reviewer_name?.trim() || null,
      rating,
      comment: values.comment?.trim() ?? ''
    }).subscribe({
      next: () => {
        this.submittingReview.set(false);
        this.reviewForm.reset({ reviewer_name: '', comment: '' });
        this.selectedRating.set(0);
        this.snackBar.open('Your review has been saved.', 'Dismiss', { duration: 3000 });
        this.loadReviews(artwork.id);
        this.http.get<Artwork>(`${API_URL}/${artwork.id}`).subscribe({
          next: (updatedArtwork) => this.artwork.set(updatedArtwork),
          error: () => this.snackBar.open('Review saved, but the summary could not be refreshed.', 'Dismiss', { duration: 4000 })
        });
      },
      error: (response) => {
        this.submittingReview.set(false);
        const message = response.error?.detail ?? 'Your review could not be saved.';
        this.snackBar.open(message, 'Dismiss', { duration: 5000 });
      }
    });
  }
}