import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.html',
  styleUrls: ['./dashboard.css']
})
export class Dashboard implements OnInit {
  portfolio: any = null;
  trades: any[] = [];

  constructor(private api: ApiService) {}

  async ngOnInit() {
    await this.loadData();
  }

  async loadData() {
    try {
      this.portfolio = await this.api.getPortfolio();
      this.trades = await this.api.getTrades();
    } catch (e) {
      console.error(e);
    }
  }
}
