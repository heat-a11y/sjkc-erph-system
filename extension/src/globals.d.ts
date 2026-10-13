// Global type declarations for Chrome extension APIs
declare global {
  interface Window {
    __erph_fillFields: ((mappings: unknown[], profile: unknown) => unknown[]) | undefined;
  }
}
export {};
