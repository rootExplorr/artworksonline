import { Routes } from '@angular/router';
import { AdminLogin } from './admin-login';
import { adminGuard } from './admin.guard';
import { ArtworkDetail } from './artwork-detail';
import { ArtworkGallery } from './artwork-gallery';
import { ArtworkManagement } from './artwork-management';
import { ArtworkUpload } from './artwork-upload';

export const routes: Routes = [
	{ path: '', redirectTo: 'artworks', pathMatch: 'full' },
	{ path: 'login', component: AdminLogin },
	{ path: 'artworks', component: ArtworkGallery },
	{
		path: 'artworks/manage',
		canActivate: [adminGuard],
		children: [
			{ path: '', component: ArtworkManagement, pathMatch: 'full' },
			{ path: 'new', component: ArtworkUpload },
			{ path: ':id/edit', component: ArtworkUpload }
		]
	},
	{ path: 'artworks/:id', component: ArtworkDetail },
	{ path: 'artworks/new', redirectTo: 'artworks/manage/new', pathMatch: 'full' },
	{ path: '**', redirectTo: 'artworks' }
];
