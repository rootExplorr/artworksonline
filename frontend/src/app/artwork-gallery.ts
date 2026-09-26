import { CurrencyPipe, DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';

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

type PriceSort = 'price_asc' | 'price_desc';

const API_URL = '/api/artworks';
const API_ORIGIN = '';

@Component({
  selector: 'app-artwork-gallery',
  imports: [
    CurrencyPipe,
    DecimalPipe,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSnackBarModule,
    RouterLink
  ],
  templateUrl: './artwork-gallery.html',
  styleUrl: './artwork-gallery.scss'
})
export class ArtworkGallery implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly snackBar = inject(MatSnackBar);

  readonly artworks = signal<Artwork[]>([]);
  readonly loading = signal(true);
  readonly sortOrder = signal<PriceSort>('price_asc');

  ngOnInit(): void {
    this.loadArtworks();
  }

  loadArtworks(sort = this.sortOrder()): void {
    this.sortOrder.set(sort);
    this.loading.set(true);
    this.http.get<Artwork[]>(API_URL, { params: { sort } }).subscribe({
      next: (artworks) => {
        this.artworks.set(artworks);
        this.loading.set(false);
      },
      error: () => {
        this.artworks.set([]);
        this.loading.set(false);
        this.snackBar.open('Could not reach the artwork service.', 'Dismiss', { duration: 4000 });
      }
    });
  }

  imageSource(path: string): string {
    return `${API_ORIGIN}${path}`;
  }
}