// Advanced caching system - implemented in v2.0.0
export class CacheManager {
  private cache: Map<string, any> = new Map();

  get(key: string) {
    return this.cache.get(key);
  }

  set(key: string, value: any) {
    this.cache.set(key, value);
  }

  clear() {
    this.cache.clear();
  }
}
