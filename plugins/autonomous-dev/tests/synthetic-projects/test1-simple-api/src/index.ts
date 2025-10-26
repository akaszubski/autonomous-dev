import express from 'express';
import { router as postsRouter } from './routes/posts';
import { router as authRouter } from './routes/auth';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

app.use('/api/posts', postsRouter);
app.use('/api/auth', authRouter);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

export default app;
