"""Tests for YCombinator and Wellfound startup crawlers."""

from ai_intel.crawlers.startups import WellfoundStartupEnricher, YCombinatorCrawler


def test_ycombinator_parse_payload() -> None:
    payload = [
        {
            "name": "Stripe",
            "slug": "stripe",
            "url": "https://www.ycombinator.com/companies/stripe",
            "website": "https://stripe.com",
            "team_size": 8000,
            "batch": "S09",
            "industry": "Fintech",
        },
        {
            "name": "Acme AI",
            "slug": "acme-ai",
            "team_size": None,
            "batch": "W24",
            "industry": "Artificial Intelligence",
        },
    ]

    startups = YCombinatorCrawler.parse_payload(payload, limit=10)

    assert len(startups) == 2
    assert startups[0].raw_name == "Stripe"
    assert str(startups[0].website_url) == "https://stripe.com/"
    assert startups[0].company_domain == "stripe.com"
    assert startups[0].employee_count == 8000
    assert startups[0].employee_count_raw == "8000"
    assert startups[0].batch == "S09"

    assert startups[1].raw_name == "Acme AI"
    assert startups[1].employee_count is None
    assert startups[1].employee_count_raw is None


def test_wellfound_parse_html() -> None:
    html = """
    <html>
      <body>
        <div>Acme Corp</div>
        <div>11-50 employees</div>
        <div>Beta Technologies</div>
        <div>5 employees</div>
      </body>
    </html>
    """

    enrichments = WellfoundStartupEnricher.parse_html(html, source_url="https://wellfound.com/jobs")

    assert "acme" in enrichments
    acme = enrichments["acme"]
    assert acme.raw_name == "Acme Corp"
    assert acme.employee_count is None  # range not converted to fake int
    assert acme.employee_count_raw == "11-50 employees"

    assert "betatechnologies" in enrichments
    beta = enrichments["betatechnologies"]
    assert beta.employee_count == 5
    assert beta.employee_count_raw == "5 employees"
