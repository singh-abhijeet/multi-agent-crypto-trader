import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../api';

@Component({
  selector: 'app-trade-controls',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './trade-controls.html',
  styleUrls: ['./trade-controls.css']
})
export class TradeControls {
  assetToTrade: string = 'BTC';
  isProcessing: boolean = false;
  lastResult: any = null;

  @Output() cycleComplete = new EventEmitter<void>();

  constructor(private api: ApiService) {}

  async triggerCycle() {
    this.isProcessing = true;
    this.lastResult = null;
    try {
      this.lastResult = await this.api.triggerCycle(this.assetToTrade);
      this.cycleComplete.emit();
    } catch (e) {
      console.error(e);
      this.lastResult = { status: 'error', message: 'Cycle failed. See console.' };
    } finally {
      this.isProcessing = false;
    }
  }
}
