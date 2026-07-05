import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';

@Component({
  selector: 'app-signed-out',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './signed-out.component.html',
  styleUrls: ['../login/login.component.scss'],
})
export class SignedOutComponent {
  constructor(private router: Router) {}

  signInAgain(): void {
    this.router.navigate(['/login']);
  }
}
