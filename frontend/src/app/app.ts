import { Component, OnInit, ViewEncapsulation, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AdminAuthService } from './admin-auth.service';

@Component({
  selector: 'app-root',
  imports: [MatButtonModule, MatIconModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './art-online.html',
  styleUrl: './art-online.scss',
  encapsulation: ViewEncapsulation.None
})
export class App implements OnInit {
  readonly auth = inject(AdminAuthService);
  private readonly router = inject(Router);

  ngOnInit(): void {
    this.auth.checkSession().subscribe();
  }

  signOut(): void {
    this.auth.logout().subscribe(() => void this.router.navigateByUrl('/artworks'));
  }
}
