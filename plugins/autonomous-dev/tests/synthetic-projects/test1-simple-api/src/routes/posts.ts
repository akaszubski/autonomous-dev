import { Router } from 'express';
import { Post } from '../models/Post';

export const router = Router();

router.get('/', async (req, res) => {
  const posts = await Post.findAll();
  res.json(posts);
});

router.get('/:id', async (req, res) => {
  const post = await Post.findById(req.params.id);
  if (!post) {
    return res.status(404).json({ error: 'Post not found' });
  }
  res.json(post);
});

router.post('/', async (req, res) => {
  const post = await Post.create(req.body);
  res.status(201).json(post);
});
