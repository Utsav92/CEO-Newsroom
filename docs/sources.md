# Sources

Validated through live HTTP fetching and RSS/Atom parsing or public metadata extraction during implementation:

| Source | Endpoint | Adapter |
| --- | --- | --- |
| OpenAI | https://openai.com/news/rss.xml | RSS |
| Meta | https://about.fb.com/news/feed/ | RSS |
| Apple | https://www.apple.com/newsroom/rss-feed.rss | RSS |
| Google | https://blog.google/rss/ | RSS |
| Anthropic | https://www.anthropic.com/news | Public announcement metadata |
| Perplexity | https://www.perplexity.ai/hub/blog | Public announcement metadata, excluding categories |
| Netflix | https://netflixtechblog.com/feed | RSS |
| NVIDIA | https://blogs.nvidia.com/feed/ | RSS |
| NVIDIA Developer | https://developer.nvidia.com/blog/feed/ | RSS |
| TechCrunch | https://techcrunch.com/feed/ | RSS |
| The Verge | https://www.theverge.com/rss/index.xml | Atom |
| Apple ML Research | https://machinelearning.apple.com/rss.xml | RSS |
| Google Research | https://research.google/blog/rss/ | RSS |
| TLDR | https://tldr.tech/archive | Newsletter metadata; TLS failure in this environment |

Availability is a point-in-time observation, not a promise. Recheck via the UI or validation script. Public-page adapters honor robots.txt and do not bypass authentication, paywalls, bot checks, or failed access. Only metadata and bounded excerpts are persisted.

Published feed references: [NVIDIA RSS](https://www.nvidia.com/en-us/about-nvidia/rss/), [Apple RSS](https://www.apple.com/ca/rss/), and [TechCrunch subscriptions](https://techcrunch.com/subscribing/). NVIDIA specifies non-commercial, personal information use. YouTube videos remain hosted on YouTube and require a server API key to discover; official handles are validated via the API before querying channel videos.
