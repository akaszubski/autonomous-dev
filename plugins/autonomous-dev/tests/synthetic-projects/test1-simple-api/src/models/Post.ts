export interface Post {
  id: string;
  title: string;
  content: string;
  authorId: string;
  createdAt: Date;
  updatedAt: Date;
}

export class Post {
  static async findAll(): Promise<Post[]> {
    // Database query logic here
    return [];
  }

  static async findById(id: string): Promise<Post | null> {
    // Database query logic here
    return null;
  }

  static async create(data: Partial<Post>): Promise<Post> {
    // Database insert logic here
    return data as Post;
  }
}
