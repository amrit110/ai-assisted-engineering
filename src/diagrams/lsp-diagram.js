/**
 * Language Server Protocol (LSP) Animated Diagram
 *
 * This module handles any dynamic interactions with the LSP diagram.
 * The primary diagram is implemented directly in the SVG in index.ejs,
 * but this module can be used to add additional interactivity or
 * perform dynamic adjustments if needed.
 */

/**
 * Initialize the LSP diagram with any dynamic behavior
 * @returns {void}
 */
export function initLSPDiagram() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupDiagram);
  } else {
    setupDiagram();
  }
}

/**
 * Sets up diagram interactivity and any dynamic features
 * @returns {void}
 */
function setupDiagram() {
  const diagram = document.getElementById('lsp-diagram');

  if (!diagram) {
    // Diagram element not found - likely not on this page
    return;
  }

  // Add event listeners or setup code here if needed in the future
  // The base animation is now handled via CSS in the SVG

  // Log for debugging in development mode
  if (process.env.NODE_ENV !== 'production') {
    console.log('LSP diagram initialized');
  }

  // Example of how to handle window resize events if needed
  handleResizeEvents(diagram);
}

/**
 * Sets up responsive behavior for the diagram
 * @param {HTMLElement} diagram - The diagram container element
 * @returns {void}
 */
function handleResizeEvents(diagram) {
  const resizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) {
      // Could add size-dependent adjustments here if needed
      if (entry.contentRect.width < 500) {
        // Example: Handle narrow viewport
      }
    }
  });

  // Start observing the diagram for resize events
  resizeObserver.observe(diagram);

  // Clean up when document is unloaded
  window.addEventListener('beforeunload', () => {
    resizeObserver.disconnect();
  });
}
