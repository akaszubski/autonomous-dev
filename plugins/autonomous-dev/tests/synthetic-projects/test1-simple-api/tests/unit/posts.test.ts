import { Post } from '../../src/models/Post';

describe('Post Model', () => {
  it('should find all posts', async () => {
    const posts = await Post.findAll();
    expect(Array.isArray(posts)).toBe(true);
  });

  it('should find post by id', async () => {
    const post = await Post.findById('123');
    expect(post).toBeDefined();
  });

  it('should create new post', async () => {
    const postData = {
      title: 'Test Post',
      content: 'Test content',
      authorId: 'user123'
    };
    const post = await Post.create(postData);
    expect(post.title).toBe('Test Post');
  });
});
