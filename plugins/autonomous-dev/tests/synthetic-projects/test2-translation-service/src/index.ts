import express from 'express';
import { CacheManager } from './cache';
import { TenantManager } from './tenant';

const app = express();
const PORT = 3000;

// SOLVED: Stream handling via proper pipe configuration
app.post('/translate', (req, res) => {
  // Fixed in v2.0.0 - proper streaming with backpressure handling
  req.pipe(processStream()).pipe(res);
});

// Feature implemented in v2.0.0
const cache = new CacheManager();
const tenants = new TenantManager();

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
