// Multi-tenant support - implemented in v2.0.0
export class TenantManager {
  private tenants: Map<string, any> = new Map();

  getTenant(id: string) {
    return this.tenants.get(id);
  }

  addTenant(id: string, config: any) {
    this.tenants.set(id, config);
  }
}
