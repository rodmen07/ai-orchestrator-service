"""
Keyword-based topic classifier for consulting prompts.
Returns a single tag that represents the primary domain of the inquiry.
Ordered from most-specific to most-general so overlapping prompts get
the most useful label (e.g. a prompt about "Terraform on AWS" → infra,
not full-stack).
"""

import re

_RULES: list[tuple[str, list[str]]] = [
    ("security", [
        "security", "soc2", "soc 2", "compliance", "audit", "owasp", "pentest",
        "vulnerability", "zero trust", "iam", "rbac", "encryption", "secret",
        "certificate", "tls", "ssl", "firewall", "intrusion",
    ]),
    ("ai", [
        r"\bai\b", r"\bml\b", "machine learning", "llm", "claude", "openai",
        "gpt", "anthropic", "model", "embedding", "vector", "inference",
        "fine.tun", "rag", "retrieval", "chatbot", "nlp",
    ]),
    ("devops", [
        "ci/cd", "cicd", "ci cd", "pipeline", "github actions", "gitlab ci",
        "jenkins", "argocd", "helm", "gitops", "rollout", "rollback",
        "deploy", "release", "artifact", "registry",
    ]),
    ("infra", [
        "aws", "gcp", "azure", "cloud run", "ec2", "s3", "rds", "lambda",
        "terraform", "kubernetes", r"\bk8s\b", "docker", "container",
        "microservice", "serverless", "fargate", "ecs", "eks", "gke",
        "vpc", "subnet", "load.balanc", "cdn", "cloudfront", "dynamo",
        "redis", "postgres", "mysql", "database", "infrastructure",
    ]),
    ("full-stack", [
        "frontend", "backend", "full.stack", "react", "vue", "angular",
        "next.js", "api", "rest", "graphql", "django", "fastapi", "flask",
        "node", "typescript", "javascript", "python", "rust", "go",
        "mobile", "ios", "android", "monolith", "migration",
    ]),
]


def classify_prompt(prompt: str) -> str:
    """Return the best-matching topic tag for the given prompt text."""
    text = prompt.lower()
    for tag, patterns in _RULES:
        for pattern in patterns:
            if re.search(pattern, text):
                return tag
    return "other"
