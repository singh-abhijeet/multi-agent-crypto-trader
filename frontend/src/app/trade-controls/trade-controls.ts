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
  isApproving: boolean = false;
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

  async resolveApproval(approved: boolean) {
    if (!this.lastResult?.thread_id) return;
    this.isApproving = true;
    try {
      const response = await this.api.approveTrade(this.lastResult.thread_id, approved);
      this.lastResult = response;
      this.cycleComplete.emit();
    } catch (e) {
      console.error(e);
      this.lastResult = { status: 'error', message: 'Failed to record decision.' };
    } finally {
      this.isApproving = false;
    }
  }
}
