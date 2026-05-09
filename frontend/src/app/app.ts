import { Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Dashboard } from './dashboard/dashboard';
import { ReasoningHub } from './reasoning-hub/reasoning-hub';
import { TradeControls } from './trade-controls/trade-controls';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, Dashboard, ReasoningHub, TradeControls],
  template: `
    <div class="app-container">
      <header>
        <h1>Crypto Trading Agent System</h1>
      </header>
      
      <main>
        <div class="left-panel">
          <app-trade-controls (cycleComplete)="refreshData()"></app-trade-controls>
          <app-dashboard></app-dashboard>
        </div>
        
        <div class="right-panel">
          <app-reasoning-hub></app-reasoning-hub>
        </div>
      </main>
    </div>
  `,
  styles: [`
    .app-container { font-family: sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
    header { border-bottom: 2px solid #333; margin-bottom: 20px; padding-bottom: 10px; }
    main { display: flex; gap: 20px; }
    .left-panel { flex: 1; }
    .right-panel { flex: 2; height: 80vh; overflow-y: auto; }
  `]
})
export class AppComponent {
  @ViewChild(Dashboard) dashboard!: Dashboard;
  @ViewChild(ReasoningHub) reasoningHub!: ReasoningHub;

  refreshData() {
    if (this.dashboard) this.dashboard.loadData();
    if (this.reasoningHub) this.reasoningHub.loadLogs();
  }
}
