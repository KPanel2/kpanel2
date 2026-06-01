import { Component, OnInit } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent implements OnInit {
  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    this.auth.session$.subscribe(session => {
      if (session === null) return; // loading state, wait
      if (session.status === 'authenticated') {
        if (this.router.url === '/login' || this.router.url === '/') {
          this.router.navigate(['/']);
        }
      } else if (!this.router.url.startsWith('/login')) {
        this.router.navigate(['/login']);
      }
    });
    this.auth.loadSession().subscribe({
      error: () => this.router.navigate(['/login']),
    });
  }
}
