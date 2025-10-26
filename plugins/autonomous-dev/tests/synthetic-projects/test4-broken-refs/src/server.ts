import express from 'express';

const app = express();

// Line 125 is referenced in documentation
app.listen(3000, () => {
  console.log('Server running');
});
