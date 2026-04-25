"""
Next.js Pattern Detector — Phase C (BUILD-7)
Identifies Next.js-specific patterns and provides iOS conversion guidance.

Covers:
- Data fetching: getServerSideProps, getStaticProps, getStaticPaths
- Routing: next/router, next/navigation, useRouter, router.push/replace/back
- Components: next/image, next/link, next/head
- Server components: 'use client' directive, implied server components
- API routes: pages/api/* and app/api/*/route.ts
- Middleware: middleware.ts/js
"""

import re
import os
from dataclasses import dataclass, field


@dataclass
class NextJsPattern:
    """A detected Next.js-specific pattern."""
    pattern_type: str   # data_fetching | routing | image | navigation | head
                        # server_component | api_route | middleware
    name: str
    line: int
    ios_equivalent: str
    conversion_difficulty: str  # auto | assisted | manual | server_only
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def detect_nextjs_patterns(content: str, relative_path: str = "") -> list[NextJsPattern]:
    """Detect all Next.js-specific patterns in a file.

    Args:
        content: Source file content
        relative_path: Relative path of the file (used to detect API routes / middleware)

    Returns:
        List of NextJsPattern instances
    """
    patterns: list[NextJsPattern] = []

    patterns.extend(_detect_data_fetching(content))
    patterns.extend(_detect_routing(content))
    patterns.extend(_detect_nextjs_imports(content))
    patterns.extend(_detect_server_components(content))

    if _is_api_route(relative_path):
        patterns.append(NextJsPattern(
            pattern_type="api_route",
            name=relative_path,
            line=1,
            ios_equivalent="Not convertible — move logic to a backend API",
            conversion_difficulty="server_only",
            details={
                "note": (
                    "Next.js API routes run server-side and have no iOS equivalent. "
                    "Host this as a standalone backend endpoint and call it via APIClient."
                ),
            },
        ))

    if _is_middleware(relative_path):
        patterns.append(NextJsPattern(
            pattern_type="middleware",
            name=relative_path,
            line=1,
            ios_equivalent="Not convertible — server-side middleware",
            conversion_difficulty="server_only",
            details={
                "note": "Middleware runs at the edge/server layer. iOS apps handle auth/routing client-side."
            },
        ))

    return patterns


# ---------------------------------------------------------------------------
# Data fetching patterns
# ---------------------------------------------------------------------------

def _detect_data_fetching(content: str) -> list[NextJsPattern]:
    patterns = []

    _SSR_FUNCS = {
        "getServerSideProps": (
            ".task { await viewModel.load() } on the View",
            "assisted",
            {
                "swift_pattern": ".task { await viewModel.load() }",
                "note": "SSR data fetching → async load on view appear via ViewModel",
            },
        ),
        "getStaticProps": (
            ".task { } or load from Bundle JSON resource",
            "assisted",
            {
                "swift_pattern": "Bundle.main resource or static JSON file decoded with JSONDecoder",
                "note": "Static props → bundle the data as a JSON asset or call an API at runtime",
            },
        ),
        "getStaticPaths": (
            "Pass route parameters as View initializer arguments",
            "assisted",
            {
                "note": "Dynamic routes → pass IDs as init params: ProductView(id: productId)",
            },
        ),
    }

    for func_name, (equiv, difficulty, details) in _SSR_FUNCS.items():
        m = re.search(
            rf"export\s+(?:async\s+)?function\s+{func_name}\b",
            content,
        )
        if m:
            line = content[: m.start()].count("\n") + 1
            patterns.append(NextJsPattern(
                pattern_type="data_fetching",
                name=func_name,
                line=line,
                ios_equivalent=equiv,
                conversion_difficulty=difficulty,
                details=details,
            ))

    return patterns


# ---------------------------------------------------------------------------
# Routing patterns
# ---------------------------------------------------------------------------

def _detect_routing(content: str) -> list[NextJsPattern]:
    patterns = []

    # next/router import
    m = re.search(r"from\s+['\"]next/router['\"]", content)
    if m:
        line = content[: m.start()].count("\n") + 1
        patterns.append(NextJsPattern(
            pattern_type="routing",
            name="next/router",
            line=line,
            ios_equivalent="NavigationPath or @Environment(\\.dismiss)",
            conversion_difficulty="assisted",
        ))

    # next/navigation import (App Router)
    m = re.search(r"from\s+['\"]next/navigation['\"]", content)
    if m:
        line = content[: m.start()].count("\n") + 1
        patterns.append(NextJsPattern(
            pattern_type="routing",
            name="next/navigation",
            line=line,
            ios_equivalent="NavigationStack + @Environment(\\.dismiss)",
            conversion_difficulty="assisted",
        ))

    # useRouter()
    for m in re.finditer(r"\buseRouter\s*\(\)", content):
        line = content[: m.start()].count("\n") + 1
        patterns.append(NextJsPattern(
            pattern_type="routing",
            name="useRouter",
            line=line,
            ios_equivalent="@Environment(\\.dismiss) private var dismiss",
            conversion_difficulty="assisted",
            details={"swift_pattern": "@Environment(\\.dismiss) private var dismiss"},
        ))

    # router.push / router.replace / router.back
    _ROUTER_METHODS = {
        "push": "navigationPath.append(destination)",
        "replace": "dismiss() then navigate to new destination",
        "back": "dismiss()",
        "prefetch": "// Not needed — iOS prefetches on demand",
    }
    for method, equiv in _ROUTER_METHODS.items():
        for m in re.finditer(rf"\brouter\.{method}\s*\(", content):
            line = content[: m.start()].count("\n") + 1
            patterns.append(NextJsPattern(
                pattern_type="routing",
                name=f"router.{method}",
                line=line,
                ios_equivalent=equiv,
                conversion_difficulty="assisted",
            ))

    return patterns


# ---------------------------------------------------------------------------
# Next.js component imports (image, link, head)
# ---------------------------------------------------------------------------

def _detect_nextjs_imports(content: str) -> list[NextJsPattern]:
    patterns = []

    _IMPORT_MAP = {
        "next/image": (
            "image",
            "AsyncImage(url:) with placeholder",
            "auto",
            {"swift_pattern": "AsyncImage(url: URL(string: src)) { image in image.resizable() }"},
        ),
        "next/link": (
            "navigation",
            "NavigationLink(destination:) or Link(url:)",
            "auto",
            {"swift_pattern": "NavigationLink(\"Label\") { DestinationView() }"},
        ),
        "next/head": (
            "head",
            ".navigationTitle() modifier or Info.plist entries",
            "assisted",
            {
                "note": "<title> → .navigationTitle(); meta tags → Info.plist or ignored",
                "swift_pattern": ".navigationTitle(\"Page Title\")",
            },
        ),
        "next/font": (
            "styling",
            "SwiftUI .font() with custom font registration",
            "assisted",
            {"note": "Register custom fonts in Info.plist, then use .font(.custom(name, size:))"},
        ),
        "next/dynamic": (
            "lazy_load",
            "Standard SwiftUI lazy loading (LazyVStack / LazyHStack)",
            "auto",
            {"note": "SwiftUI lazily loads views by default in List and LazyVStack"},
        ),
    }

    for import_path, (ptype, equiv, difficulty, details) in _IMPORT_MAP.items():
        m = re.search(rf"from\s+['\"{import_path}['\"]", content)
        if not m:
            # Also try: import X from 'next/...'
            m = re.search(rf"from\s+['\"]" + re.escape(import_path) + r"['\"]", content)
        if m:
            line = content[: m.start()].count("\n") + 1
            patterns.append(NextJsPattern(
                pattern_type=ptype,
                name=import_path,
                line=line,
                ios_equivalent=equiv,
                conversion_difficulty=difficulty,
                details=details,
            ))

    return patterns


# ---------------------------------------------------------------------------
# Server component detection
# ---------------------------------------------------------------------------

def _detect_server_components(content: str) -> list[NextJsPattern]:
    patterns = []

    # 'use client' → explicitly a client component (safe to convert normally)
    if re.match(r'\s*[\'"]use client[\'"]\s*;?', content):
        patterns.append(NextJsPattern(
            pattern_type="server_component",
            name="use_client",
            line=1,
            ios_equivalent="Standard SwiftUI View",
            conversion_difficulty="auto",
            details={
                "note": "'use client' = client component. Convert normally — no server-only patterns expected."
            },
        ))
    elif re.search(r"export\s+(?:default\s+)?(?:async\s+)?function\s+[A-Z]", content):
        # No 'use client' and exports a PascalCase function → likely a Server Component
        if not re.search(r"['\"]use client['\"]", content):
            patterns.append(NextJsPattern(
                pattern_type="server_component",
                name="server_component",
                line=1,
                ios_equivalent="SwiftUI View (server-only operations → ViewModel async methods)",
                conversion_difficulty="assisted",
                details={
                    "note": (
                        "Server Component (no 'use client'). "
                        "Async data operations must move to a ViewModel; "
                        "server-only secrets/DB access must be replaced with API calls."
                    ),
                    "warning": "Remove any direct DB queries or secret access — they have no iOS equivalent.",
                },
            ))

    return patterns


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _is_api_route(path: str) -> bool:
    """Return True if the path is a Next.js API route."""
    return bool(
        re.search(r"(?:pages[/\\]api[/\\]|app[/\\].+[/\\]route\.(ts|tsx|js|jsx)$)", path)
    )


def _is_middleware(path: str) -> bool:
    """Return True if the path is Next.js middleware."""
    return os.path.basename(path) in ("middleware.ts", "middleware.js", "middleware.tsx")


def is_nextjs_project(file_paths: list[str]) -> bool:
    """Heuristic: detect if a project is Next.js based on config files or directory structure."""
    nextjs_configs = {"next.config.js", "next.config.ts", "next.config.mjs", "next.config.cjs"}
    for path in file_paths:
        if os.path.basename(path) in nextjs_configs:
            return True
    # pages/ or app/ directories are strong indicators
    return any(re.search(r"(?:^|[/\\])(?:pages|app)[/\\]", p) for p in file_paths)


# ---------------------------------------------------------------------------
# JSX tag remappings for Next.js components
# ---------------------------------------------------------------------------

# Used by component_converter.py to recognise Next.js-specific JSX tags
# and apply the correct Swift equivalents.
NEXTJS_JSX_REMAPPINGS: dict[str, str] = {
    # next/image <Image src="..." /> → AsyncImage
    "Image": "AsyncImage_nextjs",
    # next/link <Link href="...">label</Link> → NavigationLink or Link
    "Link": "Link_nextjs",
    # next/head <Head>...</Head> → .navigationTitle() annotation
    "Head": "Head_nextjs",
}


def get_nextjs_link_href(jsx: str) -> str | None:
    """Extract the href prop from a Next.js <Link> element."""
    m = re.search(r'\bhref\s*=\s*[{"\']([^}"\']+)[}"\']', jsx)
    return m.group(1).strip("{}\"' ") if m else None
