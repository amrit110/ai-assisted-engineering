/**
 * Main diagrams module - imports and initializes all visualizations
 */

import { initCarousel } from './carousel';
import { initNeuralNetwork } from './neural-network';
import { initCustomTOC } from './toc';
import { initLSPDiagram } from './lsp-diagram';

// Initialize all visualizations
export function initVisualizations() {
  initCarousel();
  initNeuralNetwork();
  initCustomTOC();
  initLSPDiagram();
}
