import { CurrencyPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
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
}

const API_URL = '/api/artworks';
const API_ORIGIN = '';

@Component({
  selector: 'app-artwork-management',
  imports: [CurrencyPipe, MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatSnackBarModule, RouterLink],
  templateUrl: './artwork-management.html'
})
export class ArtworkManagement implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly snackBar = inject(MatSnackBar);

  readonly artworks = signal<Artwork[]>([]);
  readonly loading = signal(true);
  readonly deletingId = signal<number | null>(null);

  ngOnInit(): void {
    this.loadArtworks();
  }

  loadArtworks(): void {
    this.loading.set(true);
    this.http.get<Artwork[]>(API_URL).subscribe({
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

  removeArtwork(artwork: Artwork): void {
    if (this.deletingId() !== null || !window.confirm(`Permanently remove "${artwork.title}"?`)) {
      return;
    }

    this.deletingId.set(artwork.id);
    this.http.delete<void>(`${API_URL}/${artwork.id}`).subscribe({
      next: () => {
        this.artworks.update((artworks) => artworks.filter((item) => item.id !== artwork.id));
        this.deletingId.set(null);
        this.snackBar.open('Artwork removed.', 'Dismiss', { duration: 3000 });
      },
      error: (response) => {
        this.deletingId.set(null);
        const message = response.error?.detail ?? 'Artwork could not be removed.';
        this.snackBar.open(message, 'Dismiss', { duration: 5000 });
      }
    });
  }
}