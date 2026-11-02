"""How-to guides written as Markdown files with YAML front matter.

Public guides live in content/guides/ (committed). Private guides live in
<PRIVATE_DIR>/guides/ (never committed) and are only shown when logged in.

Front matter:
    title: Issuing a fatura-recibo
    summary: One line shown in the list
    youtube: dQw4w9WgXcQ        # YouTube video id, or…
    video: fatura-recibo.mp4    # …a file in static/videos/ or PRIVATE_DIR/videos/
    order: 10                   # Lower comes first
    category: irs               # irs | iva | ss | other
"""

from dataclasses import dataclass
from pathlib import Path

import frontmatter
import markdown


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    summary: str
    body_html: str
    public: bool
    youtube: str | None = None
    video: str | None = None
    order: int = 100
    category: str = "other"


def load_guides(directory: Path, public: bool) -> list[Guide]:
    if not directory.is_dir():
        return []
    guides = []
    for path in directory.glob("*.md"):
        post = frontmatter.load(path)
        guides.append(
            Guide(
                slug=path.stem,
                title=post.get("title", path.stem.replace("-", " ").capitalize()),
                summary=post.get("summary", ""),
                body_html=markdown.markdown(post.content, extensions=["extra"]),
                public=public,
                youtube=post.get("youtube"),
                video=post.get("video"),
                order=int(post.get("order", 100)),
                category=post.get("category", "other"),
            )
        )
    return sorted(guides, key=lambda g: (g.order, g.title))


def find_guide(directory: Path, slug: str, public: bool) -> Guide | None:
    return next((g for g in load_guides(directory, public) if g.slug == slug), None)
