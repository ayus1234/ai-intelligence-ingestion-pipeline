from __future__ import annotations

from ai_intel.crawlers.research import PapersWithCodeCrawler


def test_papers_with_code_parse_payload_groups_multiple_repos() -> None:
    payload = {
        "rows": [
            {
                "row_idx": 0,
                "row": {
                    "paper_url": "https://paperswithcode.com/paper/attention-is-all-you-need",
                    "paper_title": "Attention Is All You Need",
                    "paper_arxiv_id": "1706.03762",
                    "paper_url_abs": "https://arxiv.org/abs/1706.03762v7",
                    "repo_url": "https://github.com/tensorflow/tensor2tensor",
                    "is_official": True,
                    "mentioned_in_paper": True,
                    "mentioned_in_github": False,
                    "framework": "tf",
                },
            },
            {
                "row_idx": 1,
                "row": {
                    "paper_url": "https://paperswithcode.com/paper/attention-is-all-you-need",
                    "paper_title": "Attention Is All You Need",
                    "paper_arxiv_id": "1706.03762v7",
                    "paper_url_abs": "https://arxiv.org/abs/1706.03762v7",
                    "repo_url": "https://github.com/jadore801120/attention-is-all-you-need-pytorch/tree/master",
                    "is_official": False,
                    "mentioned_in_paper": False,
                    "mentioned_in_github": True,
                    "framework": "pytorch",
                },
            },
        ]
    }

    mappings = PapersWithCodeCrawler.parse_payload(payload)

    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping.paper_arxiv_id == "1706.03762"
    assert mapping.papers_with_code_id == "attention-is-all-you-need"
    assert [str(repo.repo_url) for repo in mapping.repositories] == [
        "https://github.com/tensorflow/tensor2tensor",
        "https://github.com/jadore801120/attention-is-all-you-need-pytorch",
    ]

