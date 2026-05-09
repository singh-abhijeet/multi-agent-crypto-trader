import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';

@Component({
  selector: 'app-reasoning-hub',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './reasoning-hub.html',
  styleUrls: ['./reasoning-hub.css']
})
export class ReasoningHub implements OnInit {
  logs: any[] = [];

  constructor(private api: ApiService) {}

  async ngOnInit() {
    await this.loadLogs();
  }

  async loadLogs() {
    try {
      this.logs = await this.api.getLogs();
    } catch (e) {
      console.error(e);
    }
  }
}
