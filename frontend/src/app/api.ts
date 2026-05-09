import { Injectable } from '@angular/core';
import axios from 'axios';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8000/api';

  async getPortfolio() {
    const res = await axios.get(`${this.baseUrl}/portfolio`);
    return res.data;
  }

  async getTrades() {
    const res = await axios.get(`${this.baseUrl}/trades`);
    return res.data;
  }

  async getLogs() {
    const res = await axios.get(`${this.baseUrl}/logs`);
    return res.data;
  }

  async triggerCycle(asset: string) {
    const res = await axios.post(`${this.baseUrl}/trigger_cycle`, { asset });
    return res.data;
  }
}
