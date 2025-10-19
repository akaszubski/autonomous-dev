# Reference Materials - Best Practices & Resources

**Purpose**: Collection of reference URLs for comparing our implementation against best practices, learning from community patterns, and staying current with Claude Code development.

**Last Updated**: 2025-10-20

---

## Official Anthropic Documentation (Priority - Always Current)

- [Claude Code Skills](https://docs.claude.com/en/docs/claude-code/skills)
- [Claude Code Sub-Agents](https://docs.claude.com/en/docs/claude-code/sub-agents)
- [Claude Code Memory](https://docs.claude.com/en/docs/claude-code/memory)
- [Prompt Engineering Overview](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview)
- [Skills Announcement](https://www.anthropic.com/news/skills)
- [Equipping Agents for Real World](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Building Agents with Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Enabling Claude Code Autonomy](https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously)
- [Anthropic Skills Repository](https://github.com/anthropics/skills)
- [GitHub Token Setup](https://github.com/settings/tokens)

---

## Community Resources (2025)

### Technical Articles

- [Supercharge ADK Development with Claude Code Skills](https://medium.com/@kazunori279/supercharge-adk-development-with-claude-code-skills-d192481cbe72)
- [Simon Willison: Claude Skills](https://simonwillison.net/2025/Oct/16/claude-skills/)
- [MediaNama: Claude Skills for AI Agents](https://www.medianama.com/2025/10/223-anthropic-claude-skills-ai-agents-specialized-tasks/)
- [Apidog: Claude Skills Guide](https://apidog.com/blog/claude-skills/)
- [Simon Willison: Multi-Agent Research System](https://simonwillison.net/2025/Jun/14/multi-agent-research-system/)
- [InfoQ: Claude Code Subagents](https://www.infoq.com/news/2025/08/claude-code-subagents/)
- [WinBuzzer: Sub-Agents Rollout](https://winbuzzer.com/2025/07/26/anthropic-rolls-out-sub-agents-for-claude-code-to-streamline-complex-ai-workflows-xcxwbn/)
- [Medium: Sub-Agents for the Masses](https://medium.com/@richardhightower/claude-code-sub-agents-agentic-programming-for-the-masses-5f6aed085333)
- [MarktechPost: Building Coding Agents](https://www.marktechpost.com/2025/04/21/anthropic-releases-a-comprehensive-guide-to-building-coding-agents-with-claude-code/)

### Comprehensive Guides

- [Complete Guide to Claude Code](https://www.siddharthbharath.com/claude-code-the-complete-guide/)
- [Builder.io: Claude Code](https://www.builder.io/blog/claude-code)
- [Apidog: CLAUDE.md Guide](https://apidog.com/blog/claude-md/)
- [NextBigFuture: Best Practices](https://www.nextbigfuture.com/2025/08/anthropic-gives-claude-coding-best-practices-one-pager.html)
- [Maximising Claude Code with CLAUDE.md](https://www.maxitect.blog/posts/maximising-claude-code-building-an-effective-claudemd)
- [eesel.ai: Best Practices](https://www.eesel.ai/blog/claude-code-best-practices)

### Tools & Analytics

- [ClaudeLog Analytics](https://claudelog.com/)

---

## Reference Repositories

### Excellent Agent Patterns

- **[wshobson/agents](https://github.com/wshobson/agents)** - Outstanding agent patterns and architecture
  - [context-manager.md](https://github.com/wshobson/agents/blob/main/agents/context-manager.md) - Context management strategies
  - Key learnings: Agent separation, context management, memory systems

### Curated Resources

- **[awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)** - Curated list of Claude Code resources
  - Skills, agents, tools, examples
  - Community contributions

---

## How We Use These References

### When Building New Features

1. **Check Official Docs First** - Anthropic's documentation is the source of truth
2. **Review Community Patterns** - See how others solved similar problems
3. **Compare Against Best Practices** - Validate our approach
4. **Test Against Reference Implementations** - Ensure compatibility

### When Troubleshooting

1. **Search for Similar Issues** - Community likely encountered it
2. **Check GitHub Discussions** - anthropics/claude-code issues
3. **Review Reference Repos** - How did wshobson handle this?
4. **Consult Best Practices** - Are we following recommended patterns?

### When Planning Architecture

1. **Read ADRs from Reference Repos** - Learn from their decisions
2. **Study Agent Patterns** - wshobson's agent separation model
3. **Review Anthropic Engineering Posts** - Official recommendations
4. **Test Against Our Use Case** - Adapt, don't copy blindly

---

## Keeping This Updated

**Monthly Review** (1st of each month):
- [ ] Check for new Anthropic documentation
- [ ] Scan for new community resources
- [ ] Update broken links
- [ ] Archive outdated references
- [ ] Add new discoveries from team

**After Major Claude Code Releases**:
- [ ] Review release notes
- [ ] Update affected documentation
- [ ] Test compatibility
- [ ] Update examples

---

## Contributing References

Found a great resource? Add it here:

1. Determine category (Official / Community / Repository)
2. Add with brief description
3. Update "Last Updated" date
4. Commit with message: `docs: add [resource name] to REFERENCES`

---

**Last Updated**: 2025-10-20
**Next Review**: 2025-11-01
